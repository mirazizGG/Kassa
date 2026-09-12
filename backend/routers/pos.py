from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload
from typing import List, Optional
from datetime import datetime, timezone, date, time

from utils.timezone import utc_now, day_start_utc, day_end_utc


# ... (imports)
from database import get_db, Sale, SaleItem, Product, Shift, Employee, Client, Payment, Expense
from schemas import SaleCreate, SaleOut, ShiftOpen, ShiftClose, ShiftOut
from core import get_current_user
from routers.audit import log_action

router = APIRouter(prefix="/pos", tags=["pos"])

CASH_METHODS = ("cash", "naqd")


async def shift_cash_payments_total(db, shift_id: int) -> float:
    """Smena davomida naqd qabul qilingan mijoz qarz to'lovlari yig'indisi."""
    from sqlalchemy import func
    total = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.shift_id == shift_id,
            Payment.payment_method.in_(CASH_METHODS),
        )
    )
    return total or 0


async def shift_cash_expenses_total(db, shift_id: int) -> float:
    """Smena davomida KASSADAN naqd chiqqan xarajatlar yig'indisi.

    Ilgari xarajatlar smena hisobiga umuman kirmasdi. Kassir kassadan pul olib
    biror narsa sotib olsa, yopilishda kassa aynan shu summaga kam chiqardi va
    undan har safar tushuntirish xati talab qilinardi. Natijada kamomad
    signali kundalik shovqinga aylanib, haqiqiy kamomadni yashirardi.
    """
    from sqlalchemy import func
    total = await db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.shift_id == shift_id,
            Expense.payment_method.in_(CASH_METHODS),
        )
    )
    return total or 0


async def shift_cash_refunds_total(db, shift: Shift) -> float:
    """Shu smenada kassadan CHIQARIB berilgan naqd vozvratlar yig'indisi.

    Faqat BOSHQA smenaga tegishli sotuvlar hisoblanadi. Agar sotuv ham, vozvrat
    ham shu smenada bo'lsa, sotuv `status = "refunded"` bo'lgani uchun yuqoridagi
    "completed" yig'indisidan allaqachon chiqib ketgan — ikkinchi marta ayirsak,
    kassa ikki barobar kam ko'rinardi.
    """
    from sqlalchemy import and_, func, not_, or_

    # Sotuv aynan shu smenaning "completed" yig'indisiga kirgan bo'lardimi?
    window = [
        Sale.cashier_id == shift.cashier_id,
        Sale.created_at >= shift.opened_at,
    ]
    if shift.closed_at:
        window.append(Sale.created_at <= shift.closed_at)
    counted_here = and_(*window)

    total = await db.scalar(
        select(func.coalesce(func.sum(Sale.cash_amount), 0)).where(
            Sale.refund_shift_id == shift.id,
            Sale.status == "refunded",
            not_(counted_here),
        )
    )
    return total or 0


async def compute_shift_totals(db, shift: Shift) -> dict:
    """Smena hisobini jonli hisoblaydi.

    Bu YAGONA hisoblash joyi. Ilgari aynan shu formula uch joyda takrorlangan
    edi (tarix, ochiq smena, yopish) va ular bir-biridan farq qila boshlagan —
    frontend kassirga bir raqamni, server boshqasini ko'rsatardi.
    """
    from sqlalchemy import func

    sales_query = select(
        func.coalesce(func.sum(
            Sale.total_amount - Sale.card_amount - Sale.transfer_amount
            - Sale.debt_amount - Sale.bonus_spent
        ), 0).label("total_cash"),
        func.coalesce(func.sum(Sale.card_amount), 0).label("total_card"),
        func.coalesce(func.sum(Sale.transfer_amount), 0).label("total_transfer"),
        func.coalesce(func.sum(Sale.debt_amount), 0).label("total_debt"),
    ).where(
        Sale.cashier_id == shift.cashier_id,
        Sale.created_at >= shift.opened_at,
        Sale.status == "completed",
    )
    if shift.closed_at:
        sales_query = sales_query.where(Sale.created_at <= shift.closed_at)

    totals = (await db.execute(sales_query)).one()
    total_cash = totals.total_cash or 0
    debt_cash = await shift_cash_payments_total(db, shift.id)
    expenses = await shift_cash_expenses_total(db, shift.id)
    refunds = await shift_cash_refunds_total(db, shift)

    return {
        "total_cash": total_cash,
        "total_card": totals.total_card or 0,
        "total_transfer": totals.total_transfer or 0,
        "total_debt": totals.total_debt or 0,
        "total_expenses": expenses,
        "total_refunds": refunds,
        # Kassada bo'lishi kerak =
        #   boshlang'ich + naqd sotuv + naqd qarz to'lovi - naqd xarajat - naqd vozvrat
        "expected_cash": (
            shift.opening_balance + total_cash + debt_cash - expenses - refunds
        ),
    }


async def totals_for_display(db, shift: Shift) -> dict:
    """Yopilgan smena uchun MUZLATILGAN qiymatlar, ochiq smena uchun jonli hisob.

    Yopilgan smenani qayta hisoblash mumkin emas: keyinroq qilingan vozvrat
    kassir imzolagan raqamni o'zgartirib yuborardi.
    """
    if shift.status == "closed" and shift.expected_cash is not None:
        return {
            "total_cash": shift.total_cash or 0,
            "total_card": shift.total_card or 0,
            "total_transfer": shift.total_transfer or 0,
            "total_debt": shift.total_debt or 0,
            "total_expenses": shift.total_expenses or 0,
            "total_refunds": shift.total_refunds or 0,
            "expected_cash": shift.expected_cash,
        }
    return await compute_shift_totals(db, shift)


def apply_totals(shift: Shift, totals: dict) -> None:
    for key, value in totals.items():
        setattr(shift, key, value)


@router.get("/shifts/history", response_model=List[ShiftOut])
async def get_shifts_history(
    limit: int = 50,
    offset: int = 0,
    employee_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get history of shifts. Admins see all, others see only their own."""
    query = select(Shift).options(joinedload(Shift.cashier))
    
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Shift.cashier_id == current_user.id)
    elif employee_id:
        query = query.where(Shift.cashier_id == employee_id)
        
    # Foydalanuvchi DO'KON kunini tanlaydi, bazada esa UTC turadi.
    if start_date:
        query = query.where(Shift.opened_at >= day_start_utc(start_date))
    if end_date:
        query = query.where(Shift.opened_at <= day_end_utc(end_date))
    
    result = await db.execute(
        query.order_by(Shift.opened_at.desc())
        .limit(limit)
        .offset(offset)
    )
    shifts = result.scalars().all()

    for shift in shifts:
        apply_totals(shift, await totals_for_display(db, shift))

    return shifts

@router.get("/shifts/active", response_model=Optional[ShiftOut])
async def get_active_shift(
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Check if the current user has an active (open) shift and return it with totals."""
    result = await db.execute(
        select(Shift)
        .where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    shift = result.scalars().first()
    
    if shift:
        apply_totals(shift, await compute_shift_totals(db, shift))

    return shift

@router.post("/shifts/open", response_model=ShiftOut)
async def open_shift(
    shift_data: ShiftOpen,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Open a new shift for the current cashier."""
    # Check if there's already an open shift
    active = await db.execute(
        select(Shift).where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    if active.scalars().first():
        raise HTTPException(status_code=400, detail="Sizda allaqachon ochiq smena bor")

    db_shift = Shift(
        cashier_id=current_user.id,
        opening_balance=shift_data.opening_balance,
        status="open",
        opened_at=utc_now(),
    )
    db.add(db_shift)
    
    await log_action(db, current_user.id, "SMENA_OCHILDI", f"Boshlang'ich balans: {shift_data.opening_balance:,.0f} so'm")
    
    await db.commit()
    await db.refresh(db_shift)
    
    # Reload with cashier info
    result = await db.execute(select(Shift).where(Shift.id == db_shift.id).options(joinedload(Shift.cashier)))
    return result.scalars().first()

@router.post("/shifts/{shift_id}/force-close", response_model=ShiftOut)
async def force_close_shift(
    shift_id: int,
    shift_data: ShiftClose,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Boshqa xodimning ochiq qolgan smenasini admin yopadi.

    Ilgari smenani FAQAT uning egasi yopa olardi. Kassir smenani yopmasdan
    ketib qolsa (kasal bo'lib qolsa, ishdan bo'shasa yoki hisobi bloklansa),
    smena abadiy ochiq qolardi: kutilgan kassa cheksiz o'sib borardi, hech
    qachon hisob-kitob qilinmasdi va o'sha kassir qayta ishga kira olmasdi.
    """
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Faqat admin yoki menejer yopa oladi")

    db_shift = await db.scalar(select(Shift).where(Shift.id == shift_id))
    if not db_shift:
        raise HTTPException(status_code=404, detail="Smena topilmadi")
    if db_shift.status != "open":
        raise HTTPException(status_code=400, detail="Bu smena allaqachon yopilgan")

    if not (shift_data.note or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Boshqa xodimning smenasini yopish sababini yozing",
        )

    db_shift.closed_at = utc_now()
    totals = await compute_shift_totals(db, db_shift)
    apply_totals(db_shift, totals)
    db_shift.cash_difference = shift_data.closing_balance - totals["expected_cash"]
    db_shift.closing_balance = shift_data.closing_balance
    db_shift.note = shift_data.note.strip()
    db_shift.closed_by = current_user.id
    db_shift.status = "closed"

    owner = await db.scalar(select(Employee).where(Employee.id == db_shift.cashier_id))
    await log_action(
        db, current_user.id, "SMENA_MAJBURIY_YOPILDI",
        f"Xodim: @{owner.username if owner else db_shift.cashier_id}. "
        f"Kutilgan: {totals['expected_cash']:,.0f} so'm. "
        f"Haqiqiy: {shift_data.closing_balance:,.0f} so'm. "
        f"Farq: {db_shift.cash_difference:,.0f} so'm. Sabab: {db_shift.note}"
    )

    await db.commit()
    await db.refresh(db_shift)
    result = await db.execute(
        select(Shift).where(Shift.id == db_shift.id).options(joinedload(Shift.cashier))
    )
    shift = result.scalars().first()
    apply_totals(shift, await totals_for_display(db, shift))
    return shift


@router.post("/shifts/close", response_model=ShiftOut)
async def close_shift(
    shift_data: ShiftClose,
    current_user: Employee = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Close the currently active shift."""
    result = await db.execute(
        select(Shift)
        .where(Shift.cashier_id == current_user.id, Shift.status == "open")
    )
    db_shift = result.scalars().first()
    
    if not db_shift:
        raise HTTPException(status_code=404, detail="Ochiq smena topilmadi")

    # Yopish vaqtini AVVAL qo'yamiz, so'ng hisoblaymiz: shunda hisob aynan shu
    # oynaga tegishli bo'ladi va keyin yozilgan sotuv unga tushmaydi.
    db_shift.closed_at = utc_now()
    totals = await compute_shift_totals(db, db_shift)
    expected_cash = totals["expected_cash"]
    cash_difference = shift_data.closing_balance - expected_cash

    if abs(cash_difference) > 0.01 and not (shift_data.note or "").strip():
        raise HTTPException(status_code=400, detail="Kassa farqi uchun sabab yozing")

    # Hisobni MUZLATAMIZ. Ilgari u har so'rovda qayta hisoblanardi va keyinroq
    # qilingan vozvrat allaqachon yopilgan smenaning kamomadini o'zgartirardi.
    apply_totals(db_shift, totals)
    db_shift.cash_difference = cash_difference
    db_shift.closing_balance = shift_data.closing_balance
    db_shift.note = (shift_data.note or "").strip() or None
    db_shift.closed_by = current_user.id
    db_shift.status = "closed"

    await log_action(
        db, current_user.id, "SMENA_YOPILDI",
        f"Kutilgan: {expected_cash:,.0f} so'm "
        f"(boshlang'ich {db_shift.opening_balance:,.0f} + naqd sotuv {totals['total_cash']:,.0f} "
        f"- naqd xarajat {totals['total_expenses']:,.0f} "
        f"- naqd vozvrat {totals['total_refunds']:,.0f}). "
        f"Haqiqiy: {shift_data.closing_balance:,.0f} so'm. Farq: {cash_difference:,.0f} so'm. "
        f"Sabab: {db_shift.note or '-'}"
    )
    
    await db.commit()
    await db.refresh(db_shift)
    
    # Reload with cashier info
    result = await db.execute(select(Shift).where(Shift.id == db_shift.id).options(joinedload(Shift.cashier)))
    shift_final = result.scalars().first()

    return shift_final
