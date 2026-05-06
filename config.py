"""
Muhit o'zgaruvchilari (environment variables) konfiguratsiyasi.
.env fayldan yoki Railway environment dan o'qiladi.
"""

import os
from dotenv import load_dotenv

# .env faylni yuklash (local development uchun)
load_dotenv()


def _require(key: str) -> str:
    """
    Majburiy env variable ni qaytaradi.
    Topilmasa — tushunarli xato chiqaradi.
    """
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Muhit o'zgaruvchisi topilmadi: {key}")
    return value


# ─────────────────────────────────────────────
# 🤖 BOT
# ─────────────────────────────────────────────

# Telegram bot token (@BotFather dan olinadi)
BOT_TOKEN: str = _require("BOT_TOKEN")

# WebApp URL (Railway webapp service URL)
# Agar yo'q bo'lsa — WebApp tugmasi ko'rsatilmaydi
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")

# ─────────────────────────────────────────────
# 🗄️ DATABASE
# ─────────────────────────────────────────────

# PostgreSQL ulanish URL
# Format: postgresql://user:password@host:port/dbname
DATABASE_URL: str = _require("DATABASE_URL")

# ─────────────────────────────────────────────
# 🤖 GEMINI API
# ─────────────────────────────────────────────

# Google Gemini API key (MT5 screenshot tahlili uchun)
# Agar yo'q bo'lsa — MT5 screenshot funksiyasi o'chiriladi
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# ─────────────────────────────────────────────
# 🌍 DEFAULTS
# ─────────────────────────────────────────────

# Default timezone (yangi foydalanuvchilar uchun)
DEFAULT_TIMEZONE: str = "Asia/Tashkent"

# Default ertalabki eslatma vaqti
DEFAULT_REMINDER_TIME: str = "08:00"

# Default avtomatik yakunlash vaqti
DEFAULT_AUTO_COMPLETE_TIME: str = "23:30"

# Default dam olish kunlari (6=Shanba, 7=Yakshanba)
DEFAULT_REST_DAYS: str = "6,7"

# ─────────────────────────────────────────────
# ⚙️ APP
# ─────────────────────────────────────────────

# WebApp server porti (Railway avtomatik beradi)
PORT: int = int(os.getenv("PORT", "8000"))

# Log darajasi
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
