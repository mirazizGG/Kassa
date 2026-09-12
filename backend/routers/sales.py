from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from database import get_db, Product, Sale, SaleItem, Employee, Client, StoreSetting, StockMove, Shift
from schemas import SaleCreate, SaleOut, RefundApproval
from core import get_current_user, verify_password, verify_approver
from utils.timezone import utc_now, shop_date, shop_today, parse_filter_date, day_bounds_utc
from routers.audit import log_action

from sqlalchemy.orm import joinedload

router = APIRouter(prefix="/sales", tags=["sales"])


async def load_sale(db, sale_id: int):
    """Javob uchun bog'lanishlari bilan chekni qayta o'qiydi.

    populate_existing=True SHART: qoldiq atomik UPDATE bilan o'zgartirilgan,
    lekin sessionmaker'da expire_on_commit=False. Usiz SQLAlchemy identity
    map'dagi ESKI Product ob'ektini qaytarardi va javobda sotuvdan OLDINGI
    qoldiq ketardi.
    """
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.cashier),
            joinedload(Sale.client),
        )
        .execution_options(populate_existing=True)
    )
    return result.unique().scalars().first()


@router.post("/", response_model=SaleOut)
async def create_sale(
    sale: SaleCreate,
    background_tasks: BackgroundTasks,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    active_shift = await db.scalar(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    # Ombochi (warehouse) sotmaydi — u faqat ombor va firmalar bilan ishlaydi.
    if current_user.role not in ["admin", "manager", "cashier"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")

    if not active_shift:
        raise HTTPException(status_code=400, detail="Savdo qilish uchun avval smenani oching")

    # Takroriy yuborishdan himoya. Kassir "To'lash" ni ikki marta bossa yoki
    # so'rov timeout bo'lib qayta ketsa, ilgari IKKITA chek yozilardi: ombordan
    # tovar ikki marta yechilar, kassaga ikki marta pul tushgandek ko'rinardi.
    if sale.idempotency_key:
        already = await db.scalar(
            select(Sale).where(Sale.idempotency_key == sale.idempotency_key)
        )
        if already:
            return await load_sale(db, already.id)

    # Nasiya yoki bonus - MIJOZSIZ bo'lishi mumkin emas.
    #
    # Ilgari `debt_amount > 0` va `client_id = null` bilan kelgan so'rov o'tib
    # ketardi: tovar ombordan chiqadi, tushum hisobga olinadi, smena kassasi
    # tiyinigacha to'g'ri keladi - va qarz HECH KIMDA paydo bo'lmaydi. Bu
    # yopilgan "fantom naqd" xatosining aynan o'zi, faqat nasiya tarafida, va
    # uni aniqlaydigan birorta hisobot yo'q edi.
    #
    # bonus_spent uchun ham xuddi shunday: chek hech kimda bo'lmagan bonus bilan
    # arzonlashardi va hech kimning balansidan yechilmasdi.
    if (sale.debt_amount > 0 or sale.bonus_spent > 0) and not sale.client_id:
        raise HTTPException(
            status_code=400,
            detail="Nasiya yoki bonus uchun mijozni tanlang",
        )

    # Mijozni SHU YERDA, hech narsa yozilmasidan oldin tekshiramiz. Ilgari
    # tekshiruv chek yozilgandan keyin turardi, shuning uchun noma'lum id
    # tushunarsiz IntegrityError (500) bo'lib chiqardi.
    client = None
    if sale.client_id:
        client = await db.scalar(select(Client).where(Client.id == sale.client_id))
        if not client:
            raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    # 1. Start a transaction implicit in async session
    
    # 2. Check stock availability
    total_amount_check = 0
    sale_items_data = []

    manager_approved = False
    for item in sale.items:
        result = await db.execute(select(Product).where(Product.id == item.product_id))
        product = result.scalars().first()
        
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")

        if item.price <= 0 or item.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"Narx va miqdor musbat bo'lishi kerak: {product.name}")

        if item.price < product.sell_price:
            if not manager_approved:
                if not sale.manager_username or not sale.manager_password:
                    raise HTTPException(status_code=403, detail="Chegirma uchun menejer tasdig'i kerak")
                await verify_approver(
                    db, current_user, sale.manager_username, sale.manager_password
                )
                manager_approved = True

        if not product.is_infinite and product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Mahsulot yetarli emas: {product.name}. Mavjud: {product.stock}")

        # Qoldiqni ATOMIK kamaytiramiz (cheksiz qoldiqlilar kamaymaydi).
        # Yuqoridagi tekshiruv faqat chiroyli xabar uchun; haqiqiy himoya —
        # shu shartli UPDATE. Ilgari bu "o'qi -> ayir -> yoz" edi: SQLite
        # yozuvlarni navbatga qo'ygani uchun muammo kam ko'rinardi, PostgreSQL
        # parallel yozadi va ikki kassa oxirgi donani sotib yubora olardi.
        if not product.is_infinite:
            stock_upd = await db.execute(
                update(Product)
                .where(Product.id == product.id, Product.stock >= item.quantity)
                .values(stock=Product.stock - item.quantity)
                .execution_options(synchronize_session=False)
            )
            if stock_upd.rowcount == 0:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Mahsulot yetarli emas: {product.name}. "
                        "Qoldiq siz tanlaganingizdan keyin o'zgardi — savatni yangilang."
                    ),
                )
        total_amount_check += item.quantity * item.price

        # Prepare item data for DB (tannarxni sotuv paytida muzlatib qo'yamiz)
        sale_items_data.append(SaleItem(
            product_id=product.id,
            quantity=item.quantity,
            price=item.price,
            buy_price=product.buy_price,
        ))

    # Chek summasi mahsulotlar yig'indisiga mos kelishini tekshiramiz (1 so'mgacha xatolik ruxsat).
    if abs(total_amount_check - sale.total_amount) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Chek summasi mahsulotlarga mos emas. Hisoblangan: {total_amount_check:,.0f}, kelgan: {sale.total_amount:,.0f}",
        )

    # To'lov qismlari yig'indisi chek summasini QOPLASHI shart.
    non_cash_sum = sale.card_amount + sale.transfer_amount + sale.debt_amount + sale.bonus_spent
    if non_cash_sum - sale.total_amount > 1:
        raise HTTPException(status_code=400, detail="Naqd bo'lmagan to'lovlar chek summasidan oshib ketdi")

    # Qolgan qismini naqd qoplashi kerak.
    #
    # DIQQAT — bu yerda jiddiy xato bor edi. Tekshiruv `if sale.cash_amount and ...`
    # ko'rinishida edi: cash_amount = 0 bo'lsa shart umuman bajarilmasdi.
    # Ya'ni 100 000 so'mlik chek 30 000 karta va 0 naqd bilan "to'liq to'langan"
    # deb qabul qilinardi, keyin quyidagi net_cash_amount qolgan 70 000 ni
    # "naqd olindi" deb yozardi. Natija: kassada bo'lmagan pul hisobga tushib,
    # smena yopilishida kassirga tushuntirib bo'lmaydigan kamomad chiqardi.
    required_cash = sale.total_amount - non_cash_sum
    if required_cash > 1 and sale.cash_amount + 1 < required_cash:
        raise HTTPException(
            status_code=400,
            detail=(
                f"To'lovlar yig'indisi chek summasidan kam. "
                f"Yana {required_cash - sale.cash_amount:,.0f} so'm kerak."
            ),
        )

    # Cash entered by the buyer can include change; persist only the net amount left in the drawer.
    net_cash_amount = max(
        0,
        sale.total_amount
        - sale.card_amount
        - sale.transfer_amount
        - sale.debt_amount
        - sale.bonus_spent,
    )

    # 3. Create Sale Record
    db_sale = Sale(
        total_amount=sale.total_amount, 
        payment_method=sale.payment_method,
        cashier_id=current_user.id,
        client_id=sale.client_id,
        status="completed",
        cash_amount=net_cash_amount,
        card_amount=sale.card_amount,
        transfer_amount=sale.transfer_amount,
        debt_amount=sale.debt_amount,
        idempotency_key=sale.idempotency_key,
    )
    db.add(db_sale)
    await db.flush() # Get ID

    # 4. Create Sale Items and Stock Logs
    for sale_item in sale_items_data:
        sale_item.sale_id = db_sale.id
        db.add(sale_item)
        
        # Log Stock Movement (Negative for sale)
        db_move = StockMove(
            product_id=sale_item.product_id,
            quantity=-sale_item.quantity,
            type="sale",
            reason=f"Sotuv (Chek ID: {db_sale.id})",
            created_by=current_user.id
        )
        db.add(db_move)

    # 5. Handle Client Balance and Bonuses (mijoz yuqorida tekshirilgan)
    if client:
        settings_res = await db.execute(select(StoreSetting).order_by(StoreSetting.id).limit(1))
        settings = settings_res.scalars().first()
        bonus_percent = settings.bonus_percentage if settings else 1.0

        # Bonus faqat qarzga yozilmagan qismdan hisoblanadi.
        paid_amount = db_sale.total_amount - db_sale.debt_amount
        earned = (paid_amount * bonus_percent) / 100 if paid_amount > 0 else 0.0

        # Sarflangan bonusni ATOMIK va SHARTLI yechamiz. Ilgari "tekshir ->
        # ayir" edi: ikki parallel sotuv bir xil bonusni ikki marta sarflab,
        # mijoz bonus balansini minusga tushira olardi.
        if sale.bonus_spent > 0:
            spent_upd = await db.execute(
                update(Client)
                .where(Client.id == client.id, Client.bonus_balance >= sale.bonus_spent)
                .values(bonus_balance=Client.bonus_balance - sale.bonus_spent)
                .execution_options(synchronize_session=False)
            )
            if spent_upd.rowcount == 0:
                raise HTTPException(status_code=400, detail="Bonus balansi yetarli emas")
            db_sale.bonus_spent = sale.bonus_spent

        # Qarz va to'plangan bonus — bitta atomik UPDATE bilan.
        deltas = {}
        if sale.debt_amount > 0:
            deltas["balance"] = Client.balance - sale.debt_amount

            # Qarz muddatini SHU YERDA qo'yamiz.
            #
            # Ilgari debt_due_date faqat CRM oynasidan qo'lda kiritilardi:
            # sotuv uni qo'ymasdi, to'lov esa tozalamasdi. Natijada bot doimiy
            # mijozga kechagi qarz uchun "muddati o'tgan" deb yozar, muddati
            # haqiqatan o'tganlar esa NULL bilan qolib, umuman xabar olmasdi.
            #
            # Mavjud muddat kelajakda bo'lsa - tegmaymiz (mijoz bilan
            # kelishilgan sana buzilmasin).
            reminder_days = settings.debt_reminder_days if settings else 3
            current_due = client.debt_due_date
            if current_due is None or shop_date(current_due) < shop_today():
                deltas["debt_due_date"] = utc_now() + timedelta(days=max(reminder_days, 1))
        if earned > 0:
            db_sale.bonus_earned = earned
            deltas["bonus_balance"] = Client.bonus_balance + earned
        if deltas:
            await db.execute(
                update(Client)
                .where(Client.id == client.id)
                .values(**deltas)
                .execution_options(synchronize_session=False)
            )

        # sessionmaker'da expire_on_commit=False — ORM ob'ekt eski balansni
        # saqlab qolardi va javobda eskirgan qiymat ketardi.
        await db.refresh(client)

    await log_action(db, current_user.id, "YANGI_SOTUV", f"Summa: {db_sale.total_amount:,.0f} so'm. Usul: {db_sale.payment_method}. Chek ID: {db_sale.id}")
    
    try:
        await db.commit()
    except IntegrityError:
        # Ikkita bir xil kalitli so'rov bir vaqtda kelgan bo'lsa, unikal indeks
        # ikkinchisini to'xtatadi. Bu xato emas — birinchisining natijasini
        # qaytaramiz.
        await db.rollback()
        if sale.idempotency_key:
            existing = await db.scalar(
                select(Sale).where(Sale.idempotency_key == sale.idempotency_key)
            )
            if existing:
                return await load_sale(db, existing.id)
        raise

    # Zahira nusxa bu yerda OLINMAYDI. Har sotuvdan keyin nusxa olish
    # clean_old_backups() ni ishga tushirib, BACKUP_RETENTION oynasini
    # "oxirgi 30 ta sotuv" ga qisqartirar edi va kunlik nusxalarni o'chirardi.
    # Nusxalar endi faqat rejaga binoan (BACKUP_HOURS) va ishga tushganda olinadi.

    return await load_sale(db, db_sale.id)

@router.get("/top-products")
async def get_top_products(
    limit: int = 12,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(
            Product.id,
            Product.name,
            Product.barcode,
            Product.sell_price,
            Product.stock,
            Product.unit,
            func.sum(SaleItem.quantity).label("sold_quantity"),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .where(Sale.status == "completed")
        .group_by(Product.id)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(min(max(limit, 1), 20))
    )
    return [dict(row._mapping) for row in rows]


@router.get("/my-daily-summary")
async def get_my_daily_summary(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # "Bugun" - DO'KON kuni. Ilgari bu yerda mintaqa qat'iy yozilgan edi va
    # SHOP_TIMEZONE sozlamasiga bo'ysunmasdi.
    start, end = day_bounds_utc(shop_today())
    result = await db.execute(
        select(
            func.count(Sale.id).label("sales_count"),
            func.coalesce(func.sum(Sale.total_amount), 0).label("total_amount"),
            func.coalesce(func.sum(Sale.cash_amount), 0).label("cash_amount"),
            func.coalesce(func.sum(Sale.card_amount), 0).label("card_amount"),
            func.coalesce(func.sum(Sale.transfer_amount), 0).label("transfer_amount"),
            func.coalesce(func.sum(Sale.debt_amount), 0).label("debt_amount"),
        ).where(
            Sale.cashier_id == current_user.id,
            Sale.status == "completed",
            Sale.created_at >= start,
            Sale.created_at < end,
        )
    )
    return dict(result.one()._mapping)
@router.get("/", response_model=List[SaleOut])
async def get_sales(
    response: Response,
    skip: int = 0,
    limit: int = 100,
    employee_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Enforce RBAC
    if current_user.role not in ["admin", "manager", "cashier"]:
        raise HTTPException(status_code=403, detail="Ruxsat berilmagan")
    if current_user.role == "cashier":
        employee_id = current_user.id
        
    start_date = parse_filter_date(start_date)
    end_date = parse_filter_date(end_date, end_of_day=True)
    
    query = (
        select(Sale)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.cashier),
            joinedload(Sale.client)
        )
    )
    if employee_id:
        query = query.where(Sale.cashier_id == employee_id)
        
    # Manager restriction: Filter out Admin sales if viewing 'all' or specific admin
    if current_user.role == "manager":
         # Join with Employee to check role of the cashier
         # This is a bit complex for a simple list, but let's just do a simple check if employee_id is provided
         if employee_id:
             target_emp = await db.scalar(select(Employee).where(Employee.id == employee_id))
             if target_emp and target_emp.role == "admin":
                 # Return empty or error? Empty seems safer for list view
                 return []
         else:
             # If listing all, exclude sales made by admins
             # We need to join with Employee table to filter by role
             query = query.join(Employee, Sale.cashier_id == Employee.id).where(Employee.role != "admin")

    if start_date:
        query = query.where(Sale.created_at >= start_date)
    if end_date:
        query = query.where(Sale.created_at <= end_date)
        
    # Jami sonni sarlavhada qaytaramiz. Ilgari sahifa faqat oxirgi 100 ta chekni
    # olardi va boshqa hech narsa ko'rsatmasdi: ko'p chekli kunda ertalabki
    # savdolar ekrandan yo'qolardi — ular bilan birga VOZVRAT tugmasi ham, chunki
    # u faqat shu ro'yxatda bor. Sanani kengaytirish yordam bermasdi.
    total = await db.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    response.headers["X-Total-Count"] = str(total or 0)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    result = await db.execute(
        query.order_by(Sale.created_at.desc())
        .offset(max(0, skip))
        .limit(max(1, min(limit, 500)))
    )
    return result.unique().scalars().all()

@router.post("/{sale_id}/refund", response_model=SaleOut)
async def refund_sale(
    sale_id: int,
    approval: RefundApproval,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Har bir vozvrat menejer/admin tasdig'ini talab qiladi.
    # verify_approver: cheklangan (5/daqiqa) va muvaffaqiyatsiz urinish jurnalga tushadi.
    approver = await verify_approver(
        db, current_user, approval.manager_username, approval.manager_password
    )

    # 1. Fetch the sale with items
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.client)
        )
    )
    db_sale = result.unique().scalars().first()
    
    if not db_sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    if db_sale.status == "refunded":
        raise HTTPException(status_code=400, detail="Sale already refunded")

    # 2. Restore stock for each item and Log
    for item in db_sale.items:
        if item.product:
            # Cheksiz qoldiqli mahsulot sotuvda kamaymagan — vozvratda ham oshmasligi kerak.
            if not item.product.is_infinite:
                await db.execute(
                    update(Product)
                    .where(Product.id == item.product_id)
                    .values(stock=Product.stock + item.quantity)
                    .execution_options(synchronize_session=False)
                )
            
            # Log Stock Movement (Positive for refund)
            db_move = StockMove(
                product_id=item.product_id,
                quantity=item.quantity,
                type="refund",
                reason=f"Vozvrat (Chek ID: {db_sale.id})",
                created_by=current_user.id
            )
            db.add(db_move)
    
    # 3. Handle Client Balance and Bonuses
    if db_sale.client:
        # Barcha teskari o'zgarishlar bitta atomik UPDATE bilan.
        reversal = {}
        if db_sale.debt_amount > 0:
            reversal["balance"] = Client.balance + db_sale.debt_amount

        bonus_delta = (db_sale.bonus_spent or 0) - (db_sale.bonus_earned or 0)
        if bonus_delta:
            reversal["bonus_balance"] = Client.bonus_balance + bonus_delta

        if reversal:
            await db.execute(
                update(Client)
                .where(Client.id == db_sale.client_id)
                .values(**reversal)
                .execution_options(synchronize_session=False)
            )
            await db.refresh(db_sale.client)

    # 4. Update Sale Status
    #
    # Vozvrat qaysi smenada bo'lganini yozib qo'yamiz: naqd pul aynan o'sha
    # smenaning kassasidan chiqadi va compute_shift_totals uni hisobga oladi.
    # Smena ochiq bo'lmasa (masalan admin kabinetdan qaytarsa) refund_shift_id
    # NULL bo'ladi — pul kassadan chiqmagan deb hisoblanadi.
    refund_shift = await db.scalar(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    db_sale.refunded_at = utc_now()
    db_sale.refund_shift_id = refund_shift.id if refund_shift else None
    db_sale.status = "refunded"
    
    await log_action(db, current_user.id, "VOZVRAT", f"Savdo qaytarildi. Chek ID: {sale_id}. Summa: {db_sale.total_amount:,.0f} so'm. Tasdiqladi: @{approver.username}")
    
    await db.commit()
    
    # Reload for response
    result = await db.execute(
        select(Sale)
        .where(Sale.id == sale_id)
        .options(
            joinedload(Sale.items).joinedload(SaleItem.product),
            joinedload(Sale.cashier),
            joinedload(Sale.client)
        )
    )
    return result.unique().scalars().first()
