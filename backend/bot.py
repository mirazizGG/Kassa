from __future__ import annotations

from database import SessionLocal as AsyncSessionLocal, Client, Employee, Attendance, StoreSetting, Product, Category, Supplier, Sale, SaleItem, Expense
from datetime import datetime, timezone
import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select, and_, func
from sqlalchemy.orm import joinedload
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- STATES ---
class Registration(StatesGroup):
    waiting_for_contact = State()
    waiting_for_name = State()

class Broadcast(StatesGroup):
    waiting_for_content = State()

dp = Dispatcher(storage=MemoryStorage())

def normalize_phone(phone: str) -> str:
    """Raqamlardan boshqa hamma narsani olib tashlash"""
    return "".join(filter(str.isdigit, str(phone)))

async def get_last_attendance_status(db, employee_id):
    stmt = select(Attendance).where(Attendance.employee_id == employee_id).order_by(Attendance.created_at.desc())
    res = await db.execute(stmt)
    last_att = res.scalars().first()
    return last_att.status if last_att else "out"

# --- MENU ---
def get_main_menu(role="client", attendance_status="out"):
    kb = []

    if role == "client":
        # Mijozlar uchun faqat shaxsiy hisob tugmalari
        kb.append([KeyboardButton(text="💰 Balansim")])
        kb.append([KeyboardButton(text="🎁 Bonuslarim")])

    elif role == "admin":
        # Admin uchun nazorat va boshqaruv
        kb.append([KeyboardButton(text="📢 Reklama yuborish")])
        kb.append([
            KeyboardButton(text="👥 Kim ishda?"),
            KeyboardButton(text="Ma'lumotlar 📦")
        ])

    elif role in ["manager", "cashier", "warehouse", "sotuvchi"]:
        # Oddiy ishchilar uchun FAQAT navbatdagi bitta amal: kelish yoki ketish
        if attendance_status == "in":
            kb.append([KeyboardButton(text="🛑 Ishdan ketish")])
        else:
            kb.append([KeyboardButton(text="🎬 Ishga kelish")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


@dp.message(F.text == "🎬 Ishga kelish")
async def clock_in_handler(message: Message) -> None:
    logging.info(f"DEBUG: Clock-in from user_id={message.from_user.id}")
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Employee).where(Employee.telegram_id == message.from_user.id))
        employee = res.scalars().first()
        logging.info(f"DEBUG: Found employee={employee.username if employee else 'None'}")
        
        if not employee:
            await message.answer("Siz xodimlar ro'yxatida yo'qsiz!")
            return
            
        # Oxirgi holatni tekshirish
        stmt = select(Attendance).where(Attendance.employee_id == employee.id).order_by(Attendance.created_at.desc())
        last_attres = await db.execute(stmt)
        last_att = last_attres.scalars().first()
        
        if last_att and last_att.status == "in":
            await message.answer("Siz allaqachon ishdasiz! 😅", reply_markup=get_main_menu(employee.role, "in"))
            return
            
        new_att = Attendance(employee_id=employee.id, status="in")
        db.add(new_att)
        await db.commit()
        name = employee.full_name or employee.username
        await message.answer(
            f"Xush kelibsiz, {name}! Ish boshlandi. 🚀\nVaqt: {datetime.now().strftime('%H:%M')}",
            reply_markup=get_main_menu(employee.role, "in"),
        )

@dp.message(F.text == "🛑 Ishdan ketish")
async def clock_out_handler(message: Message) -> None:
    logging.info(f"DEBUG: Clock-out from user_id={message.from_user.id}")
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Employee).where(Employee.telegram_id == message.from_user.id))
        employee = res.scalars().first()
        logging.info(f"DEBUG: Found employee={employee.username if employee else 'None'}")
        
        if not employee:
            await message.answer("Siz xodimlar ro'yxatida yo'qsiz!")
            return
            
        # Oxirgi holatni tekshirish
        stmt = select(Attendance).where(Attendance.employee_id == employee.id).order_by(Attendance.created_at.desc())
        last_attres = await db.execute(stmt)
        last_att = last_attres.scalars().first()
        
        if not last_att or last_att.status == "out":
            await message.answer("Siz hali ishga kelmagansiz-ku? 🤔", reply_markup=get_main_menu(employee.role, "out"))
            return
            
        new_att = Attendance(employee_id=employee.id, status="out")
        db.add(new_att)
        await db.commit()
        name = employee.full_name or employee.username
        await message.answer(
            f"Yaxshi dam oling, {name}! Ish yakunlandi. ✅\nVaqt: {datetime.now().strftime('%H:%M')}",
            reply_markup=get_main_menu(employee.role, "out"),
        )

@dp.message(F.text == "👥 Kim ishda?")
async def who_is_working_handler(message: Message) -> None:
    async with AsyncSessionLocal() as db:
        # Adminlikni tekshirish
        res = await db.execute(select(Employee).where(Employee.telegram_id == message.from_user.id, Employee.role == "admin"))
        if not res.scalars().first():
            return

        # Hozirda ishda bo'lganlarni aniqlash
        # Sodda yo'li: Har bir xodimning oxirgi statusi 'in' bo'lganlarni olish
        stmt = select(Employee)
        emp_res = await db.execute(stmt)
        all_employees = emp_res.scalars().all()
        
        working_now = []
        for emp in all_employees:
            att_stmt = select(Attendance).where(Attendance.employee_id == emp.id).order_by(Attendance.created_at.desc()).limit(1)
            att_res = await db.execute(att_stmt)
            last_att = att_res.scalars().first()
            if last_att and last_att.status == "in":
                name = emp.full_name or emp.username
                working_now.append(f"👤 {name} ({last_att.created_at.strftime('%H:%M')} dan beri)")
        
        if working_now:
            text = "👥 <b>Hozirda ishda:</b>\n\n" + "\n".join(working_now)
        else:
            text = "📭 Hozirda hech kim ishda emas."
            
        await message.answer(text, parse_mode=ParseMode.HTML)


# --- COMMANDS ---
@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    await state.clear()

    async with AsyncSessionLocal() as db:
        # Avval xodim sifatida tanilganini tekshiramiz
        emp_result = await db.execute(select(Employee).where(Employee.telegram_id == telegram_id))
        employee = emp_result.scalars().first()

        if employee:
            name = employee.full_name or employee.username
            status = await get_last_attendance_status(db, employee.id)
            await message.answer(
                f"Salom, {name}! 👋",
                reply_markup=get_main_menu(employee.role, status),
            )
            return

        # Mijoz tekshiruvi
        result = await db.execute(select(Client).where(Client.telegram_id == telegram_id))
        client = result.scalars().first()

        if client:
            await message.answer(
                f"Salom, {client.name}! 👋\nDo'konimizga xush kelibsiz.",
                reply_markup=get_main_menu("client")
            )
            return

    # Yangi foydalanuvchi - ro'yxatdan o'tkazish
    kb = [
        [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        f"Assalomu alaykum! Do'konimizga xush kelibsiz.\nRo'yxatdan o'tish uchun telefon raqamingizni yuboring.",
        reply_markup=keyboard
    )
    await state.set_state(Registration.waiting_for_contact)

@dp.message(Registration.waiting_for_contact, F.contact)
async def contact_handler(message: Message, state: FSMContext) -> None:
    contact = message.contact
    phone = contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    await state.update_data(phone=phone)

    await message.answer(
        "Rahmat! Endi iltimos, <b>Ism va Familiyangizni</b> to'liq yozib yuboring (Masalan: Eshmat Toshmatov):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name)
async def name_handler(message: Message, state: FSMContext) -> None:
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, ismingizni to'liqroq yozing.")
        return

    data = await state.get_data()
    phone = data.get("phone")
    telegram_id = message.from_user.id

    telegram_id = message.from_user.id
    norm_user_phone = normalize_phone(phone)

    async with AsyncSessionLocal() as db:
        # 1. Avval xodimlarni tekshiramiz (oxirgi 9 ta raqam bo'yicha)
        emp_result = await db.execute(select(Employee))
        employees = emp_result.scalars().all()
        
        employee = None
        for e in employees:
            if not e.phone: continue
            norm_db_phone = normalize_phone(e.phone)
            # Oxirgi 9 ta raqam mos kelsa
            if norm_user_phone[-9:] == norm_db_phone[-9:]:
                employee = e
                break

        if employee:
            logging.info(f"Linking telegram_id {telegram_id} to employee {employee.username}")
            # Xodim topildi! ID va Ismni ulab qo'yamiz
            employee.telegram_id = telegram_id
            employee.full_name = full_name
            await db.commit()
            status = await get_last_attendance_status(db, employee.id)
            await message.answer(
                f"Siz tizimda xodim sifatida tanildingiz: <b>{full_name}</b> ✅\nEndi bot orqali ish jadvalingizni boshqarishingiz mumkin.",
                reply_markup=get_main_menu(employee.role, status),
                parse_mode=ParseMode.HTML
            )
            await state.clear()
            return

        # 2. Agar xodim bo'lmasa, mijoz sifatida tekshiramiz
        client_result = await db.execute(select(Client).where(Client.phone == phone))
        client = client_result.scalars().first()

        if client:
            client.name = full_name
            client.telegram_id = telegram_id
        else:
            new_client = Client(
                name=full_name, 
                phone=phone, 
                telegram_id=telegram_id, 
                balance=0, 
                bonus_balance=0
            )
            db.add(new_client)
        
        await db.commit()
        await message.answer(f"Tabriklaymiz! Siz muvaffaqiyatli ro'yxatdan o'tdingiz. ✅", reply_markup=get_main_menu("client"))

    await state.clear()

# --- HANDLERS ---
@dp.message(F.text == "💰 Balansim")
async def balance_handler(message: Message) -> None:
    telegram_id = message.from_user.id
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Client).where(Client.telegram_id == telegram_id))
        client = result.scalars().first()

        if client:
            bal = client.balance
            text = f"👤 <b>{client.name}</b>\n\n💰 Sizning balansingiz: <b>{bal:,.0f} so'm</b>"
            if bal < 0:
                text += "\n\n🔴 Sizda qarzdorlik bor!"
            elif bal > 0:
                text += "\n\n🟢 Sizda oldindan to'lov bor."
            await message.answer(text)
        else:
            await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start ni bosing.")

@dp.message(F.text == "🎁 Bonuslarim")
async def bonus_handler(message: Message) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Client).where(Client.telegram_id == message.from_user.id))
        client = result.scalars().first()
        if client:
            text = (
                f"🎁 <b>Sizning bonuslaringiz</b>\n\n"
                f"✨ Mavjud bonus: <b>{client.bonus_balance:,.0f} so'm</b>\n\n"
                f"💡 <i>Har bir xaridingizdan bonuslar yig'iladi va ularni keyingi xaridlar uchun ishlatishingiz mumkin!</i>"
            )
            await message.answer(text)

# --- ADMIN: BROADCAST ---
@dp.message(F.text == "📢 Reklama yuborish")
async def start_broadcast(message: Message, state: FSMContext) -> None:
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Employee).where(Employee.telegram_id == message.from_user.id, Employee.role == "admin"))
        if not res.scalars().first():
            await message.answer("Kechirasiz, bu bo'lim faqat adminlar uchun!")
            return

    await message.answer(
        "📢 <b>Reklama xabari yuborish bo'limi</b>\n\n"
        "Xabar matnini yuboring (rasm bilan yuborsangiz ham bo'ladi).\n"
        "Yuborgan narsangiz barcha mijozlarga yetib boradi.\n\n"
        "<i>Bekor qilish uchun /cancel deb yozing.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Broadcast.waiting_for_content)

@dp.message(Broadcast.waiting_for_content)
async def process_broadcast(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_menu("admin"))
        return

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Client).where(Client.telegram_id.isnot(None)))
        clients = res.scalars().all()
    
    count = 0
    await message.answer(f"Xabar yuborish boshlandi ({len(clients)} ta mijoz)... ⏳")
    
    for client in clients:
        try:
            if message.content_type == "text":
                await bot.send_message(client.telegram_id, message.text)
            elif message.content_type == "photo":
                await bot.send_photo(client.telegram_id, message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == "video":
                await bot.send_video(client.telegram_id, message.video.file_id, caption=message.caption)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"Tayyor! ✅\nXabar {count} ta mijozga yuborildi.", reply_markup=get_main_menu("admin"))
    await state.clear()

# --- ADMIN: MA'LUMOTLAR (EXCEL EXPORT) ---
@dp.message(F.text == "Ma'lumotlar 📦")
async def admin_backup_handler(message: Message) -> None:
    telegram_id = message.from_user.id
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Employee).where(Employee.telegram_id == telegram_id, Employee.role == "admin"))
        admin = result.scalars().first()

        if not admin:
            return

        await message.answer("Tayyorlanmoqda... ⏳")
        try:
            import io
            import pandas as pd
            from aiogram.types import BufferedInputFile

            stamp = datetime.now().strftime("%Y%m%d_%H%M")

            def make_excel_file(df: "pd.DataFrame", sheet_name: str, filename: str) -> BufferedInputFile:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
                buf.seek(0)
                return BufferedInputFile(buf.read(), filename=filename)

            # Ombor (mahsulotlar)
            prod_res = await db.execute(select(Product))
            products = prod_res.scalars().all()
            cat_res = await db.execute(select(Category))
            category_names = {c.id: c.name for c in cat_res.scalars().all()}
            ombor_df = pd.DataFrame([
                {
                    "Nomi": p.name,
                    "Shtrix kod": p.barcode or "-",
                    "Kategoriya": category_names.get(p.category_id, "-"),
                    "Kelish narxi": p.buy_price,
                    "Sotish narxi": p.sell_price,
                    "Qoldiq": p.stock,
                    "Birlik": p.unit,
                }
                for p in products
            ])
            await bot.send_document(
                telegram_id,
                make_excel_file(ombor_df, "Ombor", f"ombor_{stamp}.xlsx"),
                caption=f"📦 Ombor ({len(products)} ta mahsulot)",
            )

            # Firmalar
            sup_res = await db.execute(select(Supplier))
            suppliers = sup_res.scalars().all()
            firma_df = pd.DataFrame([
                {
                    "Nomi": s.name,
                    "Telefon": s.phone or "-",
                    "Manzil": s.address or "-",
                    "Balans (qarzimiz)": s.balance,
                }
                for s in suppliers
            ])
            await bot.send_document(
                telegram_id,
                make_excel_file(firma_df, "Firmalar", f"firmalar_{stamp}.xlsx"),
                caption=f"🚚 Firmalar ({len(suppliers)} ta)",
            )

            # Mijozlar
            cli_res = await db.execute(select(Client))
            clients = cli_res.scalars().all()
            mijoz_df = pd.DataFrame([
                {
                    "Ismi": c.name,
                    "Telefon": c.phone or "-",
                    "Balans": c.balance,
                    "Bonus": c.bonus_balance,
                    "Qarz muddati": c.debt_due_date.strftime("%d.%m.%Y") if c.debt_due_date else "-",
                }
                for c in clients
            ])
            await bot.send_document(
                telegram_id,
                make_excel_file(mijoz_df, "Mijozlar", f"mijozlar_{stamp}.xlsx"),
                caption=f"👤 Mijozlar ({len(clients)} ta)",
            )

            # Bugungi kassirlar bo'yicha savdo taqsimoti (savdosi bo'lmaganlar ham 0 bilan chiqadi)
            today = datetime.now().date()
            start = datetime.combine(today, datetime.min.time())
            end = datetime.combine(today, datetime.max.time())

            per_cashier_res = await db.execute(
                select(
                    Employee.id,
                    Employee.full_name,
                    Employee.username,
                    func.count(Sale.id),
                    func.coalesce(func.sum(Sale.total_amount), 0),
                )
                .outerjoin(
                    Sale,
                    and_(
                        Sale.cashier_id == Employee.id,
                        Sale.created_at >= start,
                        Sale.created_at <= end,
                        Sale.status == "completed",
                    ),
                )
                .where(Employee.role != "warehouse")
                .group_by(Employee.id)
                .order_by(func.coalesce(func.sum(Sale.total_amount), 0).desc())
            )
            cashier_rows = per_cashier_res.all()
            cashier_df = pd.DataFrame([
                {
                    "Kassir": full_name or username,
                    "Cheklar soni": count,
                    "Jami summa (so'm)": total or 0,
                }
                for _, full_name, username, count, total in cashier_rows
            ])

            def sheet_name_for(label: str, used: set) -> str:
                # Excel sheet names: max 31 chars, no []:*?/\\
                safe = "".join(ch for ch in label if ch not in '[]:*?/\\')[:31] or "Kassir"
                name = safe
                i = 2
                while name in used:
                    suffix = f" ({i})"
                    name = safe[: 31 - len(suffix)] + suffix
                    i += 1
                used.add(name)
                return name

            report_buf = io.BytesIO()
            with pd.ExcelWriter(report_buf, engine="openpyxl") as writer:
                cashier_df.to_excel(writer, index=False, sheet_name="Umumiy")
                used_names = {"Umumiy"}
                for emp_id, full_name, username, count, total in cashier_rows:
                    if count == 0:
                        continue
                    label = full_name or username
                    sales_res = await db.execute(
                        select(Sale)
                        .options(joinedload(Sale.items).joinedload(SaleItem.product), joinedload(Sale.client))
                        .where(
                            Sale.cashier_id == emp_id,
                            Sale.created_at >= start,
                            Sale.created_at <= end,
                            Sale.status == "completed",
                        )
                        .order_by(Sale.created_at)
                    )
                    sales = sales_res.unique().scalars().all()
                    detail_df = pd.DataFrame([
                        {
                            "Chek №": s.id,
                            "Vaqt": s.created_at.strftime("%H:%M"),
                            "Mijoz": s.client.name if s.client else "-",
                            "Mahsulotlar": ", ".join(
                                f"{item.product.name} ({item.quantity} {item.product.unit})"
                                for item in s.items if item.product
                            ),
                            "Summa (so'm)": s.total_amount,
                            "To'lov usuli": s.payment_method,
                        }
                        for s in sales
                    ])
                    detail_df.to_excel(writer, index=False, sheet_name=sheet_name_for(label, used_names))
            report_buf.seek(0)

            await bot.send_document(
                telegram_id,
                BufferedInputFile(report_buf.read(), filename=f"kassirlar_savdosi_{stamp}.xlsx"),
                caption="🧾 Bugungi kassirlar bo'yicha savdolar (birinchi varaq — umumiy ro'yxat, keyingilari — har bir kassirning o'z cheklari)",
            )
        except Exception as e:
            await message.answer(f"Xatolik yuz berdi: {e}")

# --- QARZ ESLATMALARI ---
async def check_debts(bot: Bot | None = None):
    """Send debt reminders only when the Telegram bot is configured."""
    if not bot:
        return

    try:
        now = datetime.now()
        async with AsyncSessionLocal() as db:
            settings_result = await db.execute(select(StoreSetting))
            settings = settings_result.scalars().first()
            reminder_days = max(settings.debt_reminder_days if settings else 3, 0)
            result = await db.execute(
                select(Client).where(
                    Client.debt_due_date.isnot(None),
                    Client.telegram_id.isnot(None),
                    Client.balance < 0,
                )
            )

            for client in result.scalars().all():
                days_left = (client.debt_due_date - now).days
                debt = abs(client.balance)
                if 0 < days_left <= reminder_days:
                    msg = f"Eslatma: {client.name}, qarzingizni to'lashga {days_left} kun qoldi.\nSumma: {debt:,.0f} so'm"
                elif days_left == 0:
                    msg = f"Diqqat: {client.name}, qarzingizni to'lash muddati bugun.\nSumma: {debt:,.0f} so'm"
                elif days_left < 0:
                    msg = f"Qarzingiz muddati o'tgan: {client.name}.\nSumma: {debt:,.0f} so'm"
                else:
                    continue

                try:
                    await bot.send_message(client.telegram_id, msg)
                except Exception as exc:
                    print(f"Qarz eslatmasi yuborilmadi ({client.name}): {exc}")
    except Exception as exc:
        print(f"Qarz tekshirish xatosi: {exc}")


bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) if TOKEN else None


async def main() -> None:
    if not bot:
        logging.warning("TELEGRAM_BOT_TOKEN berilmagan: bot ishga tushmadi.")
        return
    asyncio.create_task(check_debts(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())