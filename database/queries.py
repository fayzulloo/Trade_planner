from database.connection import get_pool
from utils.logger import logger
from datetime import date, datetime


# ===== USERS =====

async def get_or_create_user(telegram_id: int, username: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", telegram_id
        )
        if row:
            return row["id"]
        row = await conn.fetchrow(
            "INSERT INTO users (telegram_id, username) VALUES ($1, $2) RETURNING id",
            telegram_id, username or ""
        )
        logger.info(f"Yangi foydalanuvchi: {telegram_id} (@{username})")
        return row["id"]


async def get_user_id(telegram_id: int) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM users WHERE telegram_id = $1", telegram_id
        )
    return row["id"] if row else None


# ===== SETTINGS =====

async def get_settings(user_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM settings WHERE user_id = $1", user_id
        )
    return dict(row) if row else None


async def is_settings_complete(user_id: int) -> bool:
    s = await get_settings(user_id)
    if not s:
        return False
    return all([s.get("starting_balance"), s.get("start_date"), s.get("total_days")])


async def upsert_setting(user_id: int, key: str, value):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM settings WHERE user_id = $1", user_id
        )
        if existing:
            await conn.execute(
                f"UPDATE settings SET {key} = $1 WHERE user_id = $2", value, user_id
            )
        else:
            await conn.execute(
                f"INSERT INTO settings (user_id, {key}) VALUES ($1, $2)", user_id, value
            )
    logger.info(f"Sozlama: user_id={user_id}, {key}={value}")


async def activate_strategy(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE settings SET is_active = TRUE WHERE user_id = $1", user_id
        )


# ===== DAILY JOURNAL =====

async def get_today_journal(user_id: int) -> dict | None:
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM daily_journal WHERE user_id = $1 AND date = $2",
            user_id, today
        )
    return dict(row) if row else None


async def get_journal_by_day(user_id: int, day_number: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM daily_journal WHERE user_id = $1 AND day_number = $2",
            user_id, day_number
        )
    return dict(row) if row else None


async def create_today_journal(user_id: int, day_number: int, start_balance: float,
                                target_profit: float, extra_target: float,
                                is_withdrawal_day: bool, withdrawal_amount: float) -> dict:
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO daily_journal
                (user_id, day_number, date, start_balance, target_profit,
                 extra_target, is_withdrawal_day, withdrawal_amount)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id, date) DO NOTHING
        """, user_id, day_number, today, start_balance, target_profit,
            extra_target, is_withdrawal_day, withdrawal_amount)
    return await get_today_journal(user_id)


async def update_journal_pnl(user_id: int):
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT day_number FROM daily_journal WHERE user_id = $1 AND date = $2",
            user_id, today
        )
        if not row:
            return
        pnl_row = await conn.fetchrow(
            "SELECT COALESCE(SUM(pnl), 0) AS total FROM trades WHERE user_id = $1 AND day_number = $2",
            user_id, row["day_number"]
        )
        await conn.execute(
            "UPDATE daily_journal SET actual_pnl = $1 WHERE user_id = $2 AND date = $3",
            float(pnl_row["total"]), user_id, today
        )


async def complete_day(user_id: int) -> dict:
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        journal = await conn.fetchrow(
            "SELECT * FROM daily_journal WHERE user_id = $1 AND date = $2",
            user_id, today
        )
        if not journal:
            return {}
        journal = dict(journal)
        end_balance = float(journal["start_balance"]) + float(journal["actual_pnl"])
        if journal["withdrawal_confirmed"]:
            end_balance -= float(journal["withdrawal_amount"])
        await conn.execute("""
            UPDATE daily_journal
            SET is_completed = TRUE, end_balance = $1, completed_at = NOW()
            WHERE user_id = $2 AND date = $3
        """, end_balance, user_id, today)
    return await get_today_journal(user_id)


async def confirm_withdrawal(user_id: int):
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE daily_journal SET withdrawal_confirmed = TRUE WHERE user_id = $1 AND date = $2",
            user_id, today
        )


async def get_journal_range(user_id: int, from_date: str, to_date: str) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM daily_journal
            WHERE user_id = $1 AND date >= $2::date AND date <= $3::date
            ORDER BY date ASC
        """, user_id, from_date, to_date)
    return [dict(r) for r in rows]


async def get_all_journals(user_id: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM daily_journal WHERE user_id = $1 ORDER BY date ASC",
            user_id
        )
    return [dict(r) for r in rows]


# ===== TRADES =====

async def add_trade(user_id: int, day_number: int, symbol: str, direction: str,
                    entry: float, exit_p: float, qty: float, pnl: float) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO trades
                (user_id, day_number, symbol, direction, entry_price, exit_price, quantity, pnl)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, user_id, day_number, symbol, direction, entry, exit_p, qty, pnl)
    logger.info(f"Savdo: user_id={user_id}, {symbol} {direction}, PnL={pnl}")
    return row["id"]


async def get_trades_by_day(user_id: int, day_number: int) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM trades WHERE user_id = $1 AND day_number = $2 ORDER BY created_at",
            user_id, day_number
        )
    return [dict(r) for r in rows]


async def get_trades_range(user_id: int, from_date: str, to_date: str) -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.* FROM trades t
            JOIN daily_journal dj ON t.user_id = dj.user_id AND t.day_number = dj.day_number
            WHERE t.user_id = $1 AND dj.date >= $2::date AND dj.date <= $3::date
            ORDER BY t.created_at ASC
        """, user_id, from_date, to_date)
    return [dict(r) for r in rows]


# ===== SCHEDULER =====

async def get_all_users_for_reminder_all() -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.telegram_id, s.reminder_time, s.timezone
            FROM settings s
            JOIN users u ON s.user_id = u.id
            WHERE s.is_active = TRUE
        """)
    return [dict(r) for r in rows]
