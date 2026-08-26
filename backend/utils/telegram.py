import os
import httpx
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")

async def send_telegram_notification(message: str):
    """Admin guruhiga xabar yuborish"""
    if not TOKEN or not ADMIN_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Telegram notification error: {e}")
