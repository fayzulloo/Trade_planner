"""
Database jadvallari va migration.
Barcha CREATE TABLE va ALTER TABLE shu yerda.
"""

import logging
from database.connection import get_pool

logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """
    Asosiy jadvallarni yaratadi (agar mavjud bo'lmasa).
    Ilova ishga tushganda bir marta chaqiriladi.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # --- users ---
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id          SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username    TEXT DEFAULT NULL,
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_users_telegram
                    ON users (telegram_id);
            """)

            # --- settings ---
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id                    SERIAL PRIMARY KEY,
                    user_id               INTEGER UNIQUE NOT NULL
                                          REFERENCES users(id) ON DELETE CASCADE,
                    starting_balance      NUMERIC(12,2) DEFAULT NULL,
                    daily_profit_rate     NUMERIC(5,4)  DEFAULT 0.20,
                    extra_target          NUMERIC(12,2) DEFAULT 0,
                    withdrawal_amount     NUMERIC(12,2) DEFAULT 0,
                    withdrawal_every      INTEGER       DEFAULT 7,
                    total_days            INTEGER       DEFAULT 7,
                    start_date            TEXT          DEFAULT NULL,
                    timezone              TEXT          DEFAULT 'Asia/Tashkent',
                    reminder_time         TEXT          DEFAULT '08:00',
                    evening_reminder_time TEXT          DEFAULT NULL,
                    auto_complete_time    TEXT          DEFAULT NULL,
                    broker_name           TEXT          DEFAULT NULL,
                    rest_days             TEXT          DEFAULT '6,7',
                    is_active             BOOLEAN       DEFAULT FALSE
                );
            """)

            # --- trades ---
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id           SERIAL PRIMARY KEY,
                    user_id      INTEGER NOT NULL
                                 REFERENCES users(id) ON DELETE CASCADE,
                    day_number   INTEGER NOT NULL,
                    symbol       TEXT    NOT NULL,
                    direction    TEXT    NOT NULL CHECK (direction IN ('BUY', 'SELL')),
                    entry_price  NUMERIC(12,5) NOT NULL,
                    exit_price   NUMERIC(12,5) NOT NULL,
                    quantity     NUMERIC(12,4) NOT NULL,
                    pnl          NUMERIC(12,2) NOT NULL,
                    swap         NUMERIC(12,2) DEFAULT 0,
                    commission   NUMERIC(12,2) DEFAULT 0,
                    open_time    TEXT          DEFAULT NULL,
                    close_time   TEXT          DEFAULT NULL,
                    order_id     TEXT          DEFAULT NULL,
                    broker       TEXT          DEFAULT NULL,
                    created_at   TIMESTAMPTZ   DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_trades_user_day
                    ON trades (user_id, day_number);
            """)

            # --- daily_journal ---
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_journal (
                    id                   SERIAL PRIMARY KEY,
                    user_id              INTEGER NOT NULL
                                         REFERENCES users(id) ON DELETE CASCADE,
                    day_number           INTEGER       NOT NULL,
                    date                 DATE          NOT NULL,
                    start_balance        NUMERIC(12,2) NOT NULL,
                    target_profit        NUMERIC(12,2) NOT NULL,
                    extra_target         NUMERIC(12,2) DEFAULT 0,
                    carry_over_amount    NUMERIC(12,2) DEFAULT 0,
                    actual_pnl           NUMERIC(12,2) DEFAULT 0,
                    net_pnl              NUMERIC(12,2) DEFAULT NULL,
                    withdrawal_amount    NUMERIC(12,2) DEFAULT 0,
                    end_balance          NUMERIC(12,2) DEFAULT NULL,
                    is_completed         BOOLEAN       DEFAULT FALSE,
                    is_withdrawal_day    BOOLEAN       DEFAULT FALSE,
                    withdrawal_confirmed BOOLEAN       DEFAULT FALSE,
                    is_rolled_over       BOOLEAN       DEFAULT FALSE,
                    completed_at         TIMESTAMPTZ   DEFAULT NULL,
                    UNIQUE (user_id, date)
                );
                CREATE INDEX IF NOT EXISTS idx_journal_user_date
                    ON daily_journal (user_id, date);
            """)

    logger.info("Barcha jadvallar tekshirildi / yaratildi.")


async def migrate_db() -> None:
    """
    Mavjud bazaga yangi ustunlar qo'shadi (agar yo'q bo'lsa).
    Har safar ishga tushganda xavfsiz ishlaydi.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:

        # (jadval, ustun, tip + default) ro'yxati
        migrations = [
            # settings
            ("settings", "extra_target",          "NUMERIC(12,2) DEFAULT 0"),
            ("settings", "reminder_time",          "TEXT DEFAULT '08:00'"),
            ("settings", "evening_reminder_time",  "TEXT DEFAULT NULL"),
            ("settings", "auto_complete_time",     "TEXT DEFAULT NULL"),
            ("settings", "broker_name",            "TEXT DEFAULT NULL"),
            ("settings", "rest_days",              "TEXT DEFAULT '6,7'"),
            # trades
            ("trades",   "open_time",              "TEXT DEFAULT NULL"),
            ("trades",   "close_time",             "TEXT DEFAULT NULL"),
            ("trades",   "order_id",               "TEXT DEFAULT NULL"),
            ("trades",   "swap",                   "NUMERIC(12,2) DEFAULT 0"),
            ("trades",   "commission",             "NUMERIC(12,2) DEFAULT 0"),
            ("trades",   "broker",                 "TEXT DEFAULT NULL"),
            # trades — sl/tp/result
            ("trades",   "sl_price",               "NUMERIC(12,5) DEFAULT NULL"),
            ("trades",   "tp_price",               "NUMERIC(12,5) DEFAULT NULL"),
            ("trades",   "result",                 "TEXT DEFAULT NULL"),
            # daily_journal
            ("daily_journal", "extra_target",      "NUMERIC(12,2) DEFAULT 0"),
            ("daily_journal", "carry_over_amount", "NUMERIC(12,2) DEFAULT 0"),
            ("daily_journal", "is_rolled_over",    "BOOLEAN DEFAULT FALSE"),
            ("daily_journal", "net_pnl",           "NUMERIC(12,2) DEFAULT NULL"),
        ]

        for table, column, definition in migrations:
            try:
                await conn.execute(f"""
                    ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition};
                """)
            except Exception as e:
                # Xato bo'lsa ham davom etadi (masalan permission issues)
                logger.error(f"Migration xato [{table}.{column}]: {e}")

    logger.info("Migration muvaffaqiyatli yakunlandi.")


async def init_db() -> None:
    """
    Baza initsializatsiyasi: jadval yaratish + migration.
    main.py da ishga tushganda chaqiriladi.
    """
    await create_tables()
    await migrate_db()
