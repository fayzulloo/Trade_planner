from database.connection import get_pool
from utils.logger import logger


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username    TEXT,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id                    SERIAL PRIMARY KEY,
                user_id               INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                starting_balance      NUMERIC(12,2),
                daily_profit_rate     NUMERIC(5,4) DEFAULT 0.20,
                extra_target          NUMERIC(12,2) DEFAULT 0,
                withdrawal_amount     NUMERIC(12,2) DEFAULT 0,
                withdrawal_every      INTEGER DEFAULT 7,
                total_days            INTEGER DEFAULT 7,
                start_date            TEXT,
                timezone              TEXT DEFAULT 'Asia/Tashkent',
                reminder_time         TEXT DEFAULT '08:00',
                evening_reminder_time TEXT DEFAULT NULL,
                auto_complete_time    TEXT DEFAULT NULL,
                broker_name           TEXT DEFAULT NULL,
                is_active             BOOLEAN DEFAULT FALSE
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id           SERIAL PRIMARY KEY,
                user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                day_number   INTEGER NOT NULL,
                symbol       TEXT NOT NULL,
                direction    TEXT NOT NULL CHECK (direction IN ('BUY', 'SELL')),
                entry_price  NUMERIC(12,5) NOT NULL,
                exit_price   NUMERIC(12,5) NOT NULL,
                quantity     NUMERIC(12,4) NOT NULL,
                pnl          NUMERIC(12,2) NOT NULL,
                open_time    TEXT,
                close_time   TEXT,
                order_id     TEXT,
                swap         NUMERIC(12,2) DEFAULT 0,
                commission   NUMERIC(12,2) DEFAULT 0,
                broker       TEXT,
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_journal (
                id                    SERIAL PRIMARY KEY,
                user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                day_number            INTEGER NOT NULL,
                date                  DATE NOT NULL,
                start_balance         NUMERIC(12,2) NOT NULL,
                target_profit         NUMERIC(12,2) NOT NULL,
                extra_target          NUMERIC(12,2) DEFAULT 0,
                actual_pnl            NUMERIC(12,2) DEFAULT 0,
                withdrawal_amount     NUMERIC(12,2) DEFAULT 0,
                end_balance           NUMERIC(12,2),
                is_completed          BOOLEAN DEFAULT FALSE,
                is_withdrawal_day     BOOLEAN DEFAULT FALSE,
                withdrawal_confirmed  BOOLEAN DEFAULT FALSE,
                completed_at          TIMESTAMPTZ,
                UNIQUE (user_id, date)
            )
        """)

        # Indekslar — query tezligi uchun
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_user_day
            ON trades(user_id, day_number)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_journal_user_date
            ON daily_journal(user_id, date)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_telegram
            ON users(telegram_id)
        """)

    logger.info("PostgreSQL jadvallar tayyor.")


async def migrate_db():
    """Yangi ustunlar qo'shish — mavjud bo'lmasa"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        migrations = [
            "ALTER TABLE settings ADD COLUMN IF NOT EXISTS extra_target NUMERIC(12,2) DEFAULT 0",
            "ALTER TABLE settings ADD COLUMN IF NOT EXISTS reminder_time TEXT DEFAULT '08:00'",
            "ALTER TABLE settings ADD COLUMN IF NOT EXISTS evening_reminder_time TEXT DEFAULT NULL",
            "ALTER TABLE settings ADD COLUMN IF NOT EXISTS auto_complete_time TEXT DEFAULT NULL",
            "ALTER TABLE daily_journal ADD COLUMN IF NOT EXISTS extra_target NUMERIC(12,2) DEFAULT 0",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS open_time TEXT",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS close_time TEXT",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS order_id TEXT",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS swap NUMERIC(12,2) DEFAULT 0",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS commission NUMERIC(12,2) DEFAULT 0",
            "ALTER TABLE trades ADD COLUMN IF NOT EXISTS broker TEXT",
            "ALTER TABLE settings ADD COLUMN IF NOT EXISTS broker_name TEXT DEFAULT NULL",
        ]
        for sql in migrations:
            try:
                await conn.execute(sql)
            except Exception as e:
                logger.warning(f"Migration skip: {e}")
    logger.info("Migration tekshiruvi tugadi.")
