from database import SessionLocal as AsyncSessionLocal, Client, Employee, Attendance
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
from sqlalchemy import select, and_
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

# --- MENU ---
def get_main_menu(role="client"):
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
    
    elif role in ["manager", "cashier", "warehouse"]:
        # Oddiy ishchilar uchun FAQAT kelib-ketish tugmalari
        kb.append([
            KeyboardButton(text="🎬 Ishga kelish"),
            KeyboardButton(text="🛑 Ishdan ketish")
        ])
    
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
            await message.answer("Siz allaqachon ishdasiz! 😅")
            return
            
        new_att = Attendance(employee_id=employee.id, status="in")
        db.add(new_att)
        await db.commit()
        name = employee.full_name or employee.username
        await message.answer(f"Xush kelibsiz, {name}! Ish boshlandi. 🚀\nVaqt: {datetime.now().strftime('%H:%M')}")

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
            await message.answer("Siz hali ishga kelmagansiz-ku? 🤔")
            return
            
        new_att = Attendance(employee_id=employee.id, status="out")
        db.add(new_att)
        await db.commit()
        name = employee.full_name or employee.username
        await message.answer(f"Yaxshi dam oling, {name}! Ish yakunlandi. ✅\nVaqt: {datetime.now().strftime('%H:%M')}")

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

    # Mijoz tekshiruvi
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Client).where(Client.telegram_id == telegram_id))
        client = result.scalars().first()

        if client:
            # Check if employee for role-based menu
            role_result = await db.execute(select(Employee).where(Employee.telegram_id == telegram_id))
            employee = role_result.scalars().first()
            role = employee.role if employee else "client"
            
            await message.answer(
                f"Salom, {client.name}! 👋\nDo'konimizga xush kelibsiz.",
                reply_markup=get_main_menu(role)
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
            await message.answer(
                f"Siz tizimda xodim sifatida tanildingiz: <b>{full_name}</b> ✅\nEndi bot orqali ish jadvalingizni boshqarishingiz mumkin.",
                reply_markup=get_main_menu(employee.role),
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

# --- ADMIN: MA'LUMOTLAR (BACKUP) ---
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
            from utils.backup import send_backup_to_telegram
            await send_backup_to_telegram(bot, telegram_id)
        except Exception as e:
            await message.answer(f"Xatolik yuz berdi: {e}")

# --- QARZ ESLATMALARI ---
async def check_debts(bot: Bot):
    """Qarz eslatmalarini tekshirish funksiyasi"""
    try:
        now = datetime.now()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Client).where(
                    Client.debt_due_date.isnot(None),
                    Client.telegram_id.isnot(None),
                    Client.balance < 0
                )
            )
            clients = result.scalars().all()

            for client in clients:
                days_left = (client.debt_due_date - now).days
                debt = abs(client.balance)

                msg = None
                if days_left == 3:
                    msg = f"🔔 Eslatma: {client.name}, qarzingizni to'lashga 3 kun qoldi.\n💰 Summa: {debt:,.0f} so'm"
                elif days_left == 2:
                    msg = f"🔔 Eslatma: {client.name}, qarzingizni to'lashga 2 kun qoldi.\n💰 Summa: {debt:,.0f} so'm"
                elif days_left == 1:
                    msg = f"⚠️ Diqqat: {client.name}, ertaga qarzingizni to'lash muddati tugaydi!\n💰 Summa: {debt:,.0f} so'm"
                elif days_left == 0:
                    msg = f"🚨 {client.name}, bugun qarzingizni to'lash muddati!\n💰 Iltimos, {debt:,.0f} so'm to'lang."
                elif days_left < 0:
                    msg = f"‼️ {client.name}, siz qarzingizni kechiktirdingiz!\n💰 Qarzingiz: {debt:,.0f} so'm.\nIltimos, tezroq to'lang."

                if msg:
                    try:
                        await bot.send_message(client.telegram_id, msg)
                    except Exception as e:
                        print(f"Xabar yuborishda xatolik ({client.name}): {e}")

    except Exception as e:
        print(f"Qarz tekshirishda xatolik: {e}")

# Initialize Bot
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def main() -> None:
    asyncio.create_task(check_debts(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
