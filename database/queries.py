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


async def save_all_settings(user_id: int, data: dict):
    """Barcha sozlamalarni bir vaqtda saqlaydi"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM settings WHERE user_id = $1", user_id
        )
        if existing:
            await conn.execute("""
                UPDATE settings SET
                    starting_balance  = $2,
                    daily_profit_rate = $3,
                    extra_target      = $4,
                    withdrawal_amount = $5,
                    withdrawal_every  = $6,
                    total_days        = $7,
                    start_date        = $8,
                    timezone          = $9,
                    reminder_time     = $10,
                    is_active         = TRUE
                WHERE user_id = $1
            """,
                user_id,
                data.get("starting_balance"),
                data.get("daily_profit_rate"),
                data.get("extra_target"),
                data.get("withdrawal_amount"),
                data.get("withdrawal_every"),
                data.get("total_days"),
                data.get("start_date"),
                data.get("timezone"),
                data.get("reminder_time"),
            )
        else:
            await conn.execute("""
                INSERT INTO settings
                    (user_id, starting_balance, daily_profit_rate, extra_target,
                     withdrawal_amount, withdrawal_every, total_days, start_date,
                     timezone, reminder_time, is_active)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,TRUE)
            """,
                user_id,
                data.get("starting_balance"),
                data.get("daily_profit_rate"),
                data.get("extra_target"),
                data.get("withdrawal_amount"),
                data.get("withdrawal_every"),
                data.get("total_days"),
                data.get("start_date"),
                data.get("timezone"),
                data.get("reminder_time"),
            )
    logger.info(f"Barcha sozlamalar saqlandi: user_id={user_id}")


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
                                is_withdrawal_day: bool, withdrawal_amount: float,
                                carry_over_amount: float = 0.0) -> dict:
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO daily_journal
                (user_id, day_number, date, start_balance, target_profit,
                 extra_target, is_withdrawal_day, withdrawal_amount, carry_over_amount)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (user_id, date) DO NOTHING
        """, user_id, day_number, today, start_balance, target_profit,
            extra_target, is_withdrawal_day, withdrawal_amount, carry_over_amount)
    return await get_today_journal(user_id)


async def update_journal_pnl(user_id: int):
    """
    Bugungi kun net PnL hisoblaydi.
    Net PnL = pnl + swap + commission (swap va commission manfiy bo'ladi)
    """
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT day_number FROM daily_journal WHERE user_id = $1 AND date = $2",
            user_id, today
        )
        if not row:
            return
        day_number = row["day_number"]
        pnl_row = await conn.fetchrow(
            """SELECT COALESCE(SUM(pnl + COALESCE(swap,0) + COALESCE(commission,0)), 0) AS total
               FROM trades
               WHERE user_id = $1
                 AND day_number = $2
                 AND DATE(created_at) = $3""",
            user_id, day_number, today
        )
        await conn.execute(
            "UPDATE daily_journal SET actual_pnl = $1 WHERE user_id = $2 AND date = $3",
            float(pnl_row["total"]), user_id, today
        )


async def complete_day(user_id: int) -> dict:
    """
    Kunni yakunlaydi.
    Agar actual_pnl < total_target bo'lsa — qolgan summa keyingi kunga rollover qilinadi.
    """
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

        actual_pnl = float(journal.get("actual_pnl") or 0)
        start_balance = float(journal.get("start_balance") or 0)
        target_profit = float(journal.get("target_profit") or 0)
        extra_target = float(journal.get("extra_target") or 0)
        carry_over_in = float(journal.get("carry_over_amount") or 0)
        total_target = target_profit + extra_target + carry_over_in
        withdrawal_amount = float(journal.get("withdrawal_amount") or 0)

        end_balance = round(start_balance + actual_pnl, 2)
        if journal.get("withdrawal_confirmed"):
            end_balance = round(end_balance - withdrawal_amount, 2)

        # Rollover hisoblash
        carry_over_out = 0.0
        is_rolled = False
        if actual_pnl < total_target:
            carry_over_out = round(total_target - actual_pnl, 2)
            is_rolled = True

        await conn.execute("""
            UPDATE daily_journal
            SET is_completed = TRUE,
                end_balance = $1,
                completed_at = NOW()
            WHERE user_id = $2 AND date = $3
        """, end_balance, user_id, today)

        # Keyingi ish kunini topib rollover qo'shamiz
        if is_rolled and carry_over_out > 0:
            await _apply_rollover(conn, user_id, journal["day_number"], carry_over_out)

    return await get_today_journal(user_id)


async def _apply_rollover(conn, user_id: int, current_day: int, carry_over: float):
    """
    Keyingi kun jurnalida carry_over_amount va is_rolled_over ni yangilaydi.
    Agar jurnal hali yaratilmagan bo'lsa — settings da total_days ni 1 ga oshiramiz.
    """
    next_day = current_day + 1

    # Keyingi kun jurnali bormi?
    existing = await conn.fetchrow(
        "SELECT id FROM daily_journal WHERE user_id = $1 AND day_number = $2",
        user_id, next_day
    )
    if existing:
        await conn.execute("""
            UPDATE daily_journal
            SET carry_over_amount = carry_over_amount + $1,
                is_rolled_over = TRUE,
                target_profit = target_profit + $1
            WHERE user_id = $2 AND day_number = $3
        """, carry_over, user_id, next_day)
    else:
        # Keyingi kun hali yaratilmagan — total_days ni oshiramiz
        await conn.execute("""
            UPDATE settings SET total_days = total_days + 1
            WHERE user_id = $1
        """, user_id)
    logger.info(f"Rollover: user={user_id}, day={current_day}→{next_day}, carry={carry_over}")


async def confirm_withdrawal(user_id: int):
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE daily_journal SET withdrawal_confirmed = TRUE WHERE user_id = $1 AND date = $2",
            user_id, today
        )


async def get_journal_range(user_id: int, from_date, to_date) -> list:
    """Faqat ish kunlarini qaytaradi (shanba/yakshanba yoq)"""
    from datetime import datetime as dt
    def to_date_obj(d):
        if hasattr(d, "year"): return d
        return dt.strptime(d, "%Y-%m-%d").date() if "-" in str(d) else dt.strptime(d, "%d.%m.%Y").date()
    from_d = to_date_obj(from_date)
    to_d = to_date_obj(to_date)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM daily_journal
            WHERE user_id = $1
              AND date >= $2
              AND date <= $3
              AND EXTRACT(DOW FROM date) NOT IN (0, 6)
            ORDER BY date ASC
        """, user_id, from_d, to_d)
    return [dict(r) for r in rows]


async def get_all_journals(user_id: int) -> list:
    """Faqat ish kunlari — strategiya hisoblash uchun"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM daily_journal
            WHERE user_id = $1
              AND EXTRACT(DOW FROM date) NOT IN (0, 6)
            ORDER BY date ASC
        """, user_id)
    return [dict(r) for r in rows]


# ===== TRADES =====

async def add_trade(user_id: int, day_number: int, symbol: str, direction: str,
                    entry: float, exit_p: float, qty: float, pnl: float,
                    open_time: str = None, close_time: str = None,
                    order_id: str = None, swap: float = 0.0,
                    commission: float = 0.0, broker: str = None) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO trades
                (user_id, day_number, symbol, direction, entry_price, exit_price,
                 quantity, pnl, open_time, close_time, order_id, swap, commission, broker)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING id
        """, user_id, day_number, symbol, direction, entry, exit_p, qty, pnl,
            open_time, close_time, order_id, swap or 0.0, commission or 0.0, broker)
    logger.info(f"Savdo: user_id={user_id}, {symbol} {direction}, PnL={pnl}, order={order_id}")
    return row["id"]


async def get_trades_by_day(user_id: int, day_number: int) -> list:
    """Faqat bugungi sanaga tegishli savdolar"""
    today = date.today()
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM trades
               WHERE user_id = $1
                 AND day_number = $2
                 AND DATE(created_at) = $3
               ORDER BY created_at""",
            user_id, day_number, today
        )
    return [dict(r) for r in rows]


async def get_trades_range(user_id: int, from_date, to_date) -> list:
    from datetime import datetime as dt
    def to_d(d):
        if hasattr(d, "year"): return d
        return dt.strptime(d, "%Y-%m-%d").date() if "-" in str(d) else dt.strptime(d, "%d.%m.%Y").date()
    from_d = to_d(from_date)
    to_d2 = to_d(to_date)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.* FROM trades t
            JOIN daily_journal dj ON t.user_id = dj.user_id AND t.day_number = dj.day_number
            WHERE t.user_id = $1
              AND dj.date >= $2
              AND dj.date <= $3
              AND EXTRACT(DOW FROM dj.date) NOT IN (0, 6)
            ORDER BY t.created_at ASC
        """, user_id, from_d, to_d2)
    return [dict(r) for r in rows]


# ===== SCHEDULER =====

async def get_all_users_for_reminder_all() -> list:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.telegram_id, s.reminder_time, s.timezone,
                   s.evening_reminder_time, s.auto_complete_time
            FROM settings s
            JOIN users u ON s.user_id = u.id
            WHERE s.is_active = TRUE
        """)
    return [dict(r) for r in rows]


async def get_real_balance(user_id: int, starting_balance: float) -> float:
    """
    Haqiqiy joriy balans:
    boshlang'ich + Σ net_pnl (pnl + swap + commission) barcha yakunlangan kunlar
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT COALESCE(SUM(pnl + COALESCE(swap,0) + COALESCE(commission,0)), 0) AS total
            FROM trades t
            JOIN daily_journal dj ON t.user_id = dj.user_id AND t.day_number = dj.day_number
            WHERE t.user_id = $1 AND dj.is_completed = TRUE
        """, user_id)
    net_total = float(row["total"] if row else 0)
    return round(float(starting_balance) + net_total, 2)


async def get_settings_rest_days(user_id: int) -> set:
    """Settings dan rest_days ni set formatida qaytaradi"""
    from utils.calculator import parse_rest_days
    s = await get_settings(user_id)
    if not s:
        return {5, 6}
    return parse_rest_days(s.get("rest_days") or "6,7")
