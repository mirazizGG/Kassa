from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import joinedload
from typing import List, Optional

import httpx

from database import get_db, Product, Category, Employee, Supply, StockMove, SaleItem
from schemas import ProductCreate, ProductUpdate, ProductOut, CategoryCreate, CategoryOut, SupplyCreate, SupplyOut, StockMoveOut, StockReturn
from core import get_current_user

from routers.audit import log_action

router = APIRouter(prefix="/inventory", tags=["inventory"])
@router.get("/purchase-list")
async def get_purchase_list(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build a live replenishment list from products below the store threshold."""
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")

    from database import StoreSetting

    settings = (await db.execute(select(StoreSetting).order_by(StoreSetting.id).limit(1))).scalars().first()
    threshold = max(settings.low_stock_threshold if settings else 5, 1)
    products = (
        await db.execute(
            select(Product)
            .where(Product.stock < threshold, Product.is_infinite == False)
            .order_by(Product.stock.asc())
        )
    ).scalars().all()

    return [
        {
            "product_id": product.id,
            "name": product.name,
            "barcode": product.barcode,
            "unit": product.unit,
            "stock": product.stock,
            "minimum_stock": threshold,
            "suggested_quantity": max(threshold * 2 - product.stock, threshold - product.stock),
            "estimated_cost": max(threshold * 2 - product.stock, threshold - product.stock) * product.buy_price,
            "priority": "critical" if product.stock <= 0 else "low",
        }
        for product in products
    ]

# --- SUPPLIES ---
@router.post("/supplies", response_model=SupplyOut)
async def create_supply(
    supply: SupplyCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # 1. Mahsulotni topish
    result = await db.execute(select(Product).where(Product.id == supply.product_id))
    product = result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. Kirim tarixi yaratish
    db_supply = Supply(
        product_id=supply.product_id,
        quantity=supply.quantity,
        buy_price=supply.buy_price
    )
    db.add(db_supply)

    # 3. Mahsulot sonini va tannarxini ATOMIK yangilash. Ilgari "o'qi -> qo'sh
    #    -> yoz" edi: bir vaqtda kelgan ikki kirimdan biri yo'qolib ketardi.
    await db.execute(
        update(Product)
        .where(Product.id == product.id)
        .values(
            stock=Product.stock + supply.quantity,
            buy_price=supply.buy_price,  # oxirgi kelgan narx
        )
        .execution_options(synchronize_session=False)
    )
    await db.refresh(product)

    # 4. Stock Movement Log
    db_move = StockMove(
        product_id=product.id,
        quantity=supply.quantity,
        type="restock",
        reason=f"Yangi kirim (ID: {db_supply.id})",
        created_by=current_user.id
    )
    db.add(db_move)

    await log_action(db, current_user.id, "OMBOR_KIRIM", f"Mahsulot: {product.name}. Soni: {supply.quantity}. Narxi: {supply.buy_price}")

    await db.commit()
    await db.refresh(db_supply)
    return db_supply

@router.get("/supplies", response_model=List[SupplyOut])
async def get_supplies(
    product_id: Optional[int] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    stmt = select(Supply).order_by(Supply.created_at.desc())
    if product_id:
        stmt = stmt.where(Supply.product_id == product_id)
    
    result = await db.execute(stmt)
    return result.scalars().all()

@router.delete("/supplies/{supply_id}")
async def delete_supply(
    supply_id: int,
    reason: str = Query(min_length=3, max_length=300, description="Bekor qilish sababi"),
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Xato kiritilgan kirimni bekor qilish.

    Kirimni tuzatishning yo'li yo'q edi. Noto'g'ri tannarx kiritilsa, u
    Product.buy_price ga yozilib qolar va o'shandan keyingi HAR BIR sotuvning
    tannarxi (SaleItem.buy_price) shu xato qiymatdan muzlatilardi — ya'ni
    keyinchalik mahsulotni tuzatish ham eski cheklarni tiklamasdi.

    Bu yerda: qoldiq kamaytiriladi, tannarx OLDINGI kirimdagi qiymatga
    qaytariladi va ombor jurnaliga tuzatish yozuvi tushadi.
    """
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Faqat admin va menejer bekor qila oladi")

    supply = await db.scalar(select(Supply).where(Supply.id == supply_id))
    if not supply:
        raise HTTPException(status_code=404, detail="Kirim topilmadi")

    product = await db.scalar(select(Product).where(Product.id == supply.product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    # Qoldiqni ATOMIK kamaytiramiz. Tovar allaqachon sotilgan bo'lsa, qoldiqni
    # minusga tushirmaymiz — bunday holatda kirimni bekor qilib bo'lmaydi.
    if not product.is_infinite:
        undo = await db.execute(
            update(Product)
            .where(Product.id == product.id, Product.stock >= supply.quantity)
            .values(stock=Product.stock - supply.quantity)
            .execution_options(synchronize_session=False)
        )
        if undo.rowcount == 0:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Bekor qilib bo'lmaydi: omborda {product.stock:g} qoldi, "
                    f"kirim esa {supply.quantity:g} edi. Tovar allaqachon sotilgan."
                ),
            )

    # Tannarxni shu mahsulotning OLDINGI kirimidagi qiymatga qaytaramiz.
    previous = await db.scalar(
        select(Supply)
        .where(Supply.product_id == supply.product_id, Supply.id != supply.id)
        .order_by(Supply.created_at.desc(), Supply.id.desc())
        .limit(1)
    )
    restored_price = previous.buy_price if previous else product.buy_price
    if previous:
        await db.execute(
            update(Product)
            .where(Product.id == product.id)
            .values(buy_price=restored_price)
            .execution_options(synchronize_session=False)
        )

    db.add(StockMove(
        product_id=product.id,
        quantity=-supply.quantity,
        type="adjustment",
        reason=f"Kirim bekor qilindi (Kirim ID: {supply_id}). Sabab: {reason}",
        created_by=current_user.id,
    ))

    await log_action(
        db, current_user.id, "KIRIM_BEKOR_QILINDI",
        f"Kirim #{supply_id} bekor qilindi: {product.name}, {supply.quantity:g} dona, "
        f"tannarx {supply.buy_price:,.0f} -> {restored_price:,.0f} so'm. Sabab: {reason}"
    )

    await db.delete(supply)
    await db.commit()
    await db.refresh(product)
    return {
        "message": "Kirim bekor qilindi",
        "new_stock": product.stock,
        "new_buy_price": product.buy_price,
    }


@router.get("/logs", response_model=List[StockMoveOut])
async def get_stock_logs(
    product_id: Optional[int] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
        
    stmt = select(StockMove).options(joinedload(StockMove.product), joinedload(StockMove.user)).order_by(StockMove.created_at.desc())
    if product_id:
        stmt = stmt.where(StockMove.product_id == product_id)
        
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/products/{product_id}/return", response_model=ProductOut)
async def return_unsold_product(
    product_id: int,
    payload: StockReturn,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return an unsold physical product to stock; cashiers may perform this with a reason."""
    if current_user.role not in ["admin", "manager", "warehouse", "cashier"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")

    product = await db.scalar(select(Product).where(Product.id == product_id))
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    await db.execute(
        update(Product)
        .where(Product.id == product.id)
        .values(stock=Product.stock + payload.quantity)
        .execution_options(synchronize_session=False)
    )
    await db.refresh(product)
    db.add(StockMove(
        product_id=product.id,
        quantity=payload.quantity,
        type="return_unsold",
        reason=f"Sotuvsiz qaytarish: {payload.reason}",
        created_by=current_user.id,
    ))
    await log_action(db, current_user.id, "SOTUVSIZ_QAYTARISH", f"Mahsulot: {product.name}. Soni: {payload.quantity}. Sabab: {payload.reason}")
    await db.commit()
    await db.refresh(product)
    return product
# --- PRODUCTS ---
@router.get("/products", response_model=List[ProductOut])
async def get_products(
    response: Response,
    category_id: Optional[int] = None,
    query: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mahsulotlar ro'yxati.

    `limit` ATAYIN majburiy emas va sukut bo'yicha YO'Q. Agar unga standart
    qiymat qo'ysak, eski chaqiruvlar jimgina qirqilib qolardi: kassa yoki
    ombor sahifasi "hammasi shu" deb ko'rsatib turgan holda katalogning bir
    qismini yashirib qo'yardi — bu auditda alohida kamchilik sifatida
    belgilangan xulq.

    Chaqiruvchi `limit` bergandagina sahifalash yoqiladi; jami son har doim
    `X-Total-Count` sarlavhasida qaytadi, shuning uchun mijoz nima
    ko'rsatilmayotganini bilib turadi.
    """
    stmt = select(Product)
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if query:
        # icontains: PostgreSQL da ILIKE, SQLite da lower() LIKE lower().
        # Oddiy .contains() LIKE beradi — SQLite registrga befarq, PostgreSQL esa yo'q,
        # ya'ni serverga ko'chganda mahsulot qidiruvi hech narsa topmay qo'yardi.
        stmt = stmt.where(Product.name.icontains(query) | Product.barcode.icontains(query))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    response.headers["X-Total-Count"] = str(total or 0)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    stmt = stmt.order_by(Product.is_favorite.desc(), Product.name)
    if limit is not None:
        stmt = stmt.limit(max(1, min(limit, 500))).offset(max(0, offset))

    result = await db.execute(stmt)
    return result.scalars().all()

# Shtrix-kod bo'yicha internetdan qidiruv natijalari uchun oddiy kesh
# (bir sessiya davomida bir kod ikki marta so'ralsa — internetga qayta chiqmaymiz).
_BARCODE_CACHE: dict[str, dict] = {}


@router.get("/barcode-lookup/{barcode}")
async def barcode_lookup(
    barcode: str,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Shtrix-kod -> mahsulot nomi.

    1) Avval o'z bazamizda qaraymiz (mahsulot allaqachon bor bo'lsa — bildiramiz).
    2) Topilmasa Open Food Facts (ochiq, bepul) bazasidan nomni olamiz.
    Internet yo'q / topilmasa — `found: false` qaytadi, xato bermaydi.
    """
    barcode = (barcode or "").strip()
    if not barcode:
        raise HTTPException(status_code=422, detail="Shtrix-kod bo'sh")

    existing = (
        await db.execute(select(Product).where(Product.barcode == barcode))
    ).scalars().first()
    if existing:
        return {
            "found": True,
            "exists": True,
            "source": "local",
            "product_id": existing.id,
            "name": existing.name,
            "brand": None,
            "image_url": None,
        }

    if barcode in _BARCODE_CACHE:
        return _BARCODE_CACHE[barcode]

    result = {"found": False, "exists": False, "source": None, "name": "", "brand": None, "image_url": None}
    url = f"https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
    params = {"fields": "product_name,product_name_ru,product_name_uz,brands,image_front_small_url,quantity"}
    try:
        async with httpx.AsyncClient(
            timeout=6.0, headers={"User-Agent": "SmartKassa POS (self-hosted)"}
        ) as client:
            resp = await client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 1:
                p = data.get("product", {}) or {}
                name = (
                    p.get("product_name_ru")
                    or p.get("product_name")
                    or p.get("product_name_uz")
                    or ""
                ).strip()
                qty = (p.get("quantity") or "").strip()
                if name and qty and qty.lower() not in name.lower():
                    name = f"{name} {qty}"
                result = {
                    "found": bool(name),
                    "exists": False,
                    "source": "openfoodfacts",
                    "name": name,
                    "brand": (p.get("brands") or "").strip() or None,
                    "image_url": p.get("image_front_small_url"),
                }
    except (httpx.HTTPError, ValueError):
        pass

    if result["found"]:
        _BARCODE_CACHE[barcode] = result
    return result


@router.post("/products", response_model=ProductOut)
async def create_product(
    product: ProductCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Takroriy shtrix-kod NOZIK xato bo'lishi kerak, 500 emas. Ilgari unikal
    # cheklov buzilishi ushlanmasdi va operator "Ichki server xatoligi" degan
    # tushunarsiz xabar olardi.
    if product.barcode:
        existing = await db.scalar(
            select(Product).where(Product.barcode == product.barcode)
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Bu shtrix-kod band: \"{existing.name}\"",
            )

    db_product = Product(**product.model_dump())
    db.add(db_product)
    # flush SHART: usiz db_product.id hali NULL bo'ladi va quyidagi ombor
    # harakati product_id = NULL bilan yozilib, hech qaysi mahsulotga
    # bog'lanmay qolardi.
    await db.flush()

    # Stock Log if initial stock > 0
    if db_product.stock > 0:
        db_move = StockMove(
            product_id=db_product.id,
            quantity=db_product.stock,
            type="adjustment",
            reason="Dastlabki qoldiq (mahsulot yaratilganda)",
            created_by=current_user.id
        )
        db.add(db_move)

    await log_action(db, current_user.id, "YANGI_MAHSULOT", f"Mahsulot: {db_product.name}. Sklad: {db_product.stock}. Narx: {db_product.sell_price}")

    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    product: ProductUpdate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    result = await db.execute(select(Product).where(Product.id == product_id))
    db_product = result.scalars().first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    old_stock = db_product.stock
    new_stock = product.stock

    # Optimistik qulf: tahrirlash oynasi ochiq turganda tovar sotilgan bo'lsa,
    # eski qoldiqni qayta yozib yubormaymiz. Ilgari forma yuklangan paytdagi
    # qiymat shunchaki ustidan yozilardi — oradagi sotuvlar bekor bo'lib,
    # omborga "Ombor tahrirlandi (adjustment)" degan yolg'on tuzatish tushardi.
    if (
        product.expected_stock is not None
        and abs(product.expected_stock - old_stock) > 1e-9
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Qoldiq siz formani ochganingizdan keyin o'zgardi "
                f"({product.expected_stock:g} -> {old_stock:g}). "
                "Sahifani yangilab, qaytadan urinib ko'ring."
            ),
        )

    # Qoldiqni ATOMIK va SHARTLI yozamiz (compare-and-swap).
    #
    # Yuqoridagi tekshiruv formani ochgan paytdagi qiymatni solishtiradi, ammo
    # tekshiruv bilan commit orasida ham sotuv bo'lishi mumkin. Shuning uchun
    # yozuvning o'zi ham shartli: qoldiq oradan o'zgargan bo'lsa rowcount 0
    # bo'ladi va biz sotuvlarni bekor qilib yubormaymiz.
    if product.expected_stock is not None and new_stock != old_stock:
        stock_upd = await db.execute(
            update(Product)
            .where(Product.id == product_id, Product.stock == product.expected_stock)
            .values(stock=new_stock)
            .execution_options(synchronize_session=False)
        )
        if stock_upd.rowcount == 0:
            raise HTTPException(
                status_code=409,
                detail="Qoldiq hozirgina o'zgardi. Sahifani yangilab, qaytadan urinib ko'ring.",
            )
        await db.refresh(db_product)

    # Qolgan maydonlar (expected_stock ustun emas, qoldiq yuqorida yozildi)
    for key, value in product.model_dump(exclude={"expected_stock", "stock"}).items():
        setattr(db_product, key, value)

    # expected_stock berilmagan bo'lsa — eski xulq: qoldiqni to'g'ridan-to'g'ri
    # yozamiz (masalan ombor inventarizatsiyasi).
    if product.expected_stock is None:
        db_product.stock = new_stock

    # Stock Log if stock changed
    if old_stock != new_stock:
        diff = new_stock - old_stock
        db_move = StockMove(
            product_id=db_product.id,
            quantity=diff,
            type="adjustment",
            reason="Ombor tahrirlandi (adjustment)",
            created_by=current_user.id
        )
        db.add(db_move)

    await log_action(db, current_user.id, "MAHSULOT_TAHRIR", f"Mahsulot: {db_product.name} (ID: {product_id}). Sklad: {old_stock} -> {new_stock}")

    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Only admins and managers can delete products")

    result = await db.execute(select(Product).where(Product.id == product_id))
    db_product = result.scalars().first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    # Tarixga bog'langan mahsulotni O'CHIRIB BO'LMAYDI.
    #
    # Ilgari tekshiruv yo'q edi. SQLite tashqi kalitlarni majburlamagani uchun
    # sotuv satrlari "yetim" bo'lib qolardi, keyin SQLite o'sha id ni yangi
    # mahsulotga qayta berib yuborardi va eski cheklar boshqa tovarga ishora
    # qila boshlardi. Bundan tashqari hisobotdagi tannarx INNER JOIN orqali
    # olingani uchun o'chirilgan mahsulotning tannarxi yo'qolib, sof foyda
    # sun'iy ravishda oshib ketardi. PostgreSQL da esa bu chaqiruv
    # IntegrityError bilan 500 qaytarardi.
    sold = await db.scalar(
        select(func.count(SaleItem.id)).where(SaleItem.product_id == product_id)
    )
    if sold:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bu mahsulot {sold} ta chekda ishlatilgan — o'chirib bo'lmaydi. "
                "Sotuvdan olib qo'yish uchun qoldiqni 0 qiling."
            ),
        )

    supplied = await db.scalar(
        select(func.count(Supply.id)).where(Supply.product_id == product_id)
    )
    if supplied:
        raise HTTPException(
            status_code=409,
            detail=f"Bu mahsulotda {supplied} ta kirim tarixi bor — o'chirib bo'lmaydi.",
        )

    # Qoldiq harakatlari tarix emas, mahsulotning o'ziga tegishli — ular ketishi mumkin.
    await db.execute(delete(StockMove).where(StockMove.product_id == product_id))
    await db.delete(db_product)
    
    # Audit Log
    try:
        from routers.audit import log_action
        await log_action(db, current_user.id, "DELETE_PRODUCT", f"Mahsulot o'chirildi: {db_product.name} (ID: {product_id})")
    except:
        pass

    await db.commit()
    return {"status": "success", "message": "Product deleted"}

# --- CATEGORIES ---
@router.get("/categories", response_model=List[CategoryOut])
async def get_categories(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Category))
    return result.scalars().all()

@router.post("/categories", response_model=CategoryOut)
async def create_category(
    category: CategoryCreate,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    db_category = Category(name=category.name)
    db.add(db_category)
    await log_action(db, current_user.id, "YANGI_KATEGORIYA", f"Kategoriya: {category.name}")
    await db.commit()
    await db.refresh(db_category)
    return db_category
@router.post("/products/{product_id}/toggle-favorite", response_model=ProductOut)
async def toggle_favorite(
    product_id: int,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role not in ["admin", "manager", "warehouse", "cashier"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    result = await db.execute(select(Product).where(Product.id == product_id))
    db_product = result.scalars().first()

    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")

    db_product.is_favorite = not db_product.is_favorite
    await db.commit()
    await db.refresh(db_product)
    return db_product
