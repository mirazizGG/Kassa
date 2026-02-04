import os
import shutil
from datetime import datetime
import glob

# Baza fayli joylashuvi
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "market.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

def create_backup():
    """Ma'lumotlar bazasidan nusxa oladi (Backup)"""
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)

        # Fayl nomi (vaqt bilan)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_name)

        # Nusxa olish
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, backup_path)
            print(f"✅ Zahira nusxasi yaratildi: {backup_name}")
            
            # Eski zahiralarni tozalash (faqat oxirgi 20tasini qoldirish)
            clean_old_backups()
            return backup_path
    except Exception as e:
        print(f"❌ Zahira olishda xatolik: {e}")
    return None

def clean_old_backups(limit=20):
    """Eski zahiralarni o'chirib yuboradi (joy tejash uchun)"""
    try:
        backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "backup_*.db")))
        if len(backups) > limit:
            files_to_delete = backups[:-limit]
            for f in files_to_delete:
                os.remove(f)
            print(f"🧹 {len(files_to_delete)} ta eski zahiralar tozalandi.")
    except Exception as e:
        print(f"❌ Tozalashda xatolik: {e}")

async def send_backup_to_telegram(bot, admin_id):
    """Zahira faylini Telegramga yuboradi"""
    from aiogram.types import FSInputFile
    
    backup_path = create_backup()
    if backup_path and bot and admin_id:
        try:
            document = FSInputFile(backup_path)
            await bot.send_document(
                admin_id, 
                document, 
                caption=f"📦 <b>Avtomatik Zahira (Auto-Backup)</b>\n📅 Vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
            )
            print(f"📤 Zahira Telegramga yuborildi.")
        except Exception as e:
            print(f"❌ Telegramga yuborishda xatolik: {e}")
