import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from sqlalchemy import select
from database import SessionLocal as AsyncSessionLocal, Client
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- STATES ---
class Registration(StatesGroup):
    waiting_for_contact = State()
    waiting_for_name = State()

dp = Dispatcher(storage=MemoryStorage())

# --- MENU ---
def get_main_menu():
    kb = [
        [KeyboardButton(text="💰 Balansim")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- COMMANDS ---
@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id

    # Mijoz tekshiruvi
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Client).where(Client.telegram_id == telegram_id))
        client = result.scalars().first()

        if client:
            await message.answer(
                f"Salom, {client.name}! 👋\nSiz avval ro'yxatdan o'tgansiz.",
                reply_markup=get_main_menu()
            )
            await state.clear()
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

    async with AsyncSessionLocal() as db:
        # Telefon bo'yicha tekshirish
        result = await db.execute(select(Client).where(Client.phone == phone))
        existing_client = result.scalars().first()

        if existing_client:
            existing_client.name = full_name
            existing_client.telegram_id = message.from_user.id
            await db.commit()
            await message.answer(f"Siz avval ro'yxatdan o'tgansiz. Ma'lumotlaringiz yangilandi! ✅", reply_markup=get_main_menu())
        else:
            new_client = Client(name=full_name, phone=phone, telegram_id=message.from_user.id, balance=0)
            db.add(new_client)
            await db.commit()
            await message.answer(f"Tabriklaymiz! Siz muvaffaqiyatli ro'yxatdan o'tdingiz. ✅", reply_markup=get_main_menu())

    await state.clear()

# --- BALANS ---
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
                if client.debt_due_date:
                    days_left = (client.debt_due_date - datetime.now()).days
                    if days_left > 0:
                        text += f"\n📅 To'lov muddati: {days_left} kun qoldi"
                    elif days_left == 0:
                        text += f"\n⚠️ To'lov muddati: BUGUN!"
                    else:
                        text += f"\n‼️ Muddat {abs(days_left)} kun o'tdi!"
            elif bal > 0:
                text += "\n\n🟢 Sizda oldindan to'lov bor."
            await message.answer(text)
        else:
            await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start ni bosing.")

# --- QARZ ESLATMALARI ---
async def check_debts(bot: Bot):
    """Qarz eslatmalarini tekshirish - har soatda, faqat ertalab 9:00 da yuborish"""
    while True:
        try:
            now = datetime.now()

            # Faqat ertalab 9:00 da yuborish
            if now.hour == 9 and now.minute < 5:
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

        await asyncio.sleep(3600)  # Har soatda tekshirish

# Initialize Bot
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def main() -> None:
    asyncio.create_task(check_debts(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
