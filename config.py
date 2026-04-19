import os
from dotenv import load_dotenv
from utils.logger import logger

load_dotenv()


def validate_config():
    errors = []

    token = os.getenv("BOT_TOKEN")
    if not token:
        errors.append("BOT_TOKEN topilmadi!")
    elif len(token) < 30:
        errors.append("BOT_TOKEN noto'g'ri formatda!")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        errors.append("DATABASE_URL topilmadi!")
    elif not db_url.startswith("postgresql"):
        errors.append("DATABASE_URL postgresql:// bilan boshlanishi kerak!")

    if errors:
        for e in errors:
            logger.critical(f"Config xatosi: {e}")
        raise ValueError("Config tekshiruvidan o'tmadi:\n" + "\n".join(errors))

    logger.info("Config tekshiruvi muvaffaqiyatli o'tdi.")
    return token, db_url


BOT_TOKEN, DATABASE_URL = validate_config()

# Railway PostgreSQL URL ni asyncpg formatiga o'tkazish
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

CHARTS_DIR = "charts"
os.makedirs(CHARTS_DIR, exist_ok=True)

