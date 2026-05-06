"""
Barcha database CRUD operatsiyalari.
Har bir funksiya o'z try/except blokiga ega.
"""

import logging
from datetime import date
from typing import Optional
from asyncpg import Record

from database.connection import get_pool

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 👤 USER
# ─────────────────────────────────────────────

async def get_or_create_user(telegram_id: int, username: Optional[str] = None) -> Record:
    """
    Foydalanuvchini topadi yoki yangi yaratadi.
    Qaytaradi: users jadvali yozuvi.
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Avval settings yaratish uchun user kerak, shuning uchun upsert ishlatamiz
            user = await conn.fetchrow("""
                INSERT INTO users (telegram_id, username)
                VALUES ($1, $2)
                ON CONFLICT (telegram_id) DO UPDATE
                    SET username = EXCLUDED.username
                RETURNING *;
            """, telegram_id, username)

            # Settings avtomatik yaratiladi (agar yo'q bo'lsa)
            await conn.execute("""
                INSERT INTO settings (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING;
            """, user["id"])

            return user
    except Exception as e:
        logger.error(f"get_or_create_user xato [tg_id={telegram_id}]: {e}")
        raise


# ─────────────────────────────────────────────
# ⚙️ SETTINGS
# ─────────────────────────────────────────────

async def get_settings(user_id: int) -> Optional[Record]:
    """
    Foydalanuvchi sozlamalarini qaytaradi.
    user_id — users.id (telegram_id emas!).
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT * FROM settings WHERE user_id = $1;
            """, user_id)
    except Exception as e:
        logger.error(f"get_settings xato [user_id={user_id}]: {e}")
        raise


async def save_settings(user_id: int, **kwargs) -> None:
    """
    Foydalanuvchi sozlamalarini yangilaydi.
    Faqat uzatilgan maydonlar yangilanadi.

    Misol: save_settings(user_id, starting_balance=1000, daily_profit_rate=0.10)
    """
    if not kwargs:
        return

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Dinamik SET qismi yaratish
            fields = list(kwargs.keys())
            values = list(kwargs.values())

            set_clause = ", ".join(
                f"{field} = ${i + 2}" for i, field in enumerate(fields)
            )

            await conn.execute(f"""
                UPDATE settings SET {set_clause}
                WHERE user_id = $1;
            """, user_id, *values)
    except Exception as e:
        logger.error(f"save_settings xato [user_id={user_id}]: {e}")
        raise


# ─────────────────────────────────────────────
# 📝 TRADES
# ─────────────────────────────────────────────

async def add_trade(
    user_id: int,
    day_number: int,
    symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    quantity: float,
    pnl: float,
    swap: float = 0,
    commission: float = 0,
    open_time: Optional[str] = None,
    close_time: Optional[str] = None,
    order_id: Optional[str] = None,
    broker: Optional[str] = None,
) -> Record:
    """
    Yangi savdo yozuvini qo'shadi.
    daily_journal.actual_pnl ni ham yangilaydi.
    Qaytaradi: yaratilgan trade yozuvi.
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                trade = await conn.fetchrow("""
                    INSERT INTO trades (
                        user_id, day_number, symbol, direction,
                        entry_price, exit_price, quantity, pnl,
                        swap, commission, open_time, close_time,
                        order_id, broker
                    ) VALUES (
                        $1, $2, $3, $4,
                        $5, $6, $7, $8,
                        $9, $10, $11, $12,
                        $13, $14
                    ) RETURNING *;
                """, user_id, day_number, symbol, direction,
                    entry_price, exit_price, quantity, pnl,
                    swap, commission, open_time, close_time,
                    order_id, broker)

                # Bugungi journal actual_pnl ni yangilash
                # ⚠️ Diqqat: actual_pnl faqat pnl (swap/commission siz)
                await conn.execute("""
                    UPDATE daily_journal
                    SET actual_pnl = actual_pnl + $1
                    WHERE user_id = $2 AND day_number = $3;
                """, pnl, user_id, day_number)

                return trade
    except Exception as e:
        logger.error(f"add_trade xato [user_id={user_id}]: {e}")
        raise


async def get_trades_by_day(user_id: int, day_number: int) -> list[Record]:
    """
    Berilgan kun savdolarini qaytaradi.
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            return await conn.fetch("""
                SELECT * FROM trades
                WHERE user_id = $1 AND day_number = $2
                ORDER BY created_at ASC;
            """, user_id, day_number)
    except Exception as e:
        logger.error(f"get_trades_by_day xato [user_id={user_id}, day={day_number}]: {e}")
        raise


async def get_trades_sum_by_day(user_id: int, day_number: int) -> dict:
    """
    Kun savdolari yig'indisini qaytaradi.
    Qaytaradi: {'actual_pnl': ..., 'net_pnl': ...}

    actual_pnl = faqat pnl yig'indisi
    net_pnl    = pnl + swap + commission yig'indisi
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COALESCE(SUM(pnl), 0)                                       AS actual_pnl,
                    COALESCE(SUM(pnl + COALESCE(swap,0) + COALESCE(commission,0)), 0) AS net_pnl
                FROM trades
                WHERE user_id = $1 AND day_number = $2;
            """, user_id, day_number)
            return dict(row)
    except Exception as e:
        logger.error(f"get_trades_sum_by_day xato [user_id={user_id}, day={day_number}]: {e}")
        raise


# ─────────────────────────────────────────────
# 📅 DAILY JOURNAL
# ─────────────────────────────────────────────

async def get_today_journal(user_id: int, today: date) -> Optional[Record]:
    """
    Bugungi jurnal yozuvini qaytaradi.
    Agar yaratilmagan bo'lsa None qaytaradi.
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            return await conn.fetchrow("""
                SELECT * FROM daily_journal
                WHERE user_id = $1 AND date = $2;
            """, user_id, today)
    except Exception as e:
        logger.error(f"get_today_journal xato [user_id={user_id}]: {e}")
        raise


async def create_journal_day(
    user_id: int,
    day_number: int,
    today: date,
    start_balance: float,
    target_profit: float,
    extra_target: float = 0,
    withdrawal_amount: float = 0,
    is_withdrawal_day: bool = False,
) -> Record:
    """
    Yangi kun jurnal yozuvini yaratadi.

    carry_over_amount bu yerda parametr sifatida qabul qilinmaydi.
    Balki oldingi kunning yakunlangan ma'lumotlaridan avtomatik hisoblanadi:
      - day_number == 1 bo'lsa → carry_over = 0 (strategiya 1-kuni, oldingi kun yo'q)
      - Oldingi kun is_rolled_over = TRUE bo'lsa:
          carry_over = total_target - net_pnl (ya'ni bajarilmagan qoldiq)
      - Oldingi kun is_rolled_over = FALSE bo'lsa → carry_over = 0

    ON CONFLICT (user_id, date) — ikki marta yaratishdan himoyalangan,
    mavjud yozuvni o'zgartirmaydi.

    Qaytaradi: yaratilgan yoki mavjud yozuv.
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # --- Carry over hisoblash ---
            carry_over = 0.0

            # ⚠️ Filtr: 1-kun bo'lsa oldingi kun yo'q, carry_over = 0
            if day_number > 1:
                prev = await conn.fetchrow("""
                    SELECT
                        is_rolled_over,
                        is_completed,
                        target_profit,
                        extra_target,
                        carry_over_amount,
                        net_pnl
                    FROM daily_journal
                    WHERE user_id = $1 AND day_number = $2;
                """, user_id, day_number - 1)

                if prev and prev["is_completed"] and prev["is_rolled_over"]:
                    prev_total_target = (
                        float(prev["target_profit"]) +
                        float(prev["extra_target"]) +
                        float(prev["carry_over_amount"])
                    )
                    prev_net_pnl = float(prev["net_pnl"] or 0)
                    carry_over = max(0.0, prev_total_target - prev_net_pnl)

            # --- Journal yaratish ---
            return await conn.fetchrow("""
                INSERT INTO daily_journal (
                    user_id, day_number, date,
                    start_balance, target_profit, extra_target,
                    carry_over_amount, withdrawal_amount, is_withdrawal_day
                ) VALUES (
                    $1, $2, $3,
                    $4, $5, $6,
                    $7, $8, $9
                )
                ON CONFLICT (user_id, date) DO NOTHING
                RETURNING *;
            """, user_id, day_number, today,
                start_balance, target_profit, extra_target,
                carry_over, withdrawal_amount, is_withdrawal_day)
    except Exception as e:
        logger.error(f"create_journal_day xato [user_id={user_id}, date={today}]: {e}")
        raise


async def complete_day(user_id: int, day_number: int) -> Optional[Record]:
    """
    Kunni yakunlaydi:
    1. Savdolar net_pnl ni hisoblaydi
    2. end_balance ni yangilaydi
    3. is_rolled_over ni belgilaydi (maqsad bajarilmasa)

    ⚠️ Diqqat: carry_over bu yerda saqlanmaydi.
    Scheduler 00:01 da create_journal_day chaqirganda
    oldingi kunning is_rolled_over va end_balance dan
    carry_over o'zi hisoblanadi.

    Qaytaradi: yangilangan journal yozuvi.
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # 1. Bugungi journal
                journal = await conn.fetchrow("""
                    SELECT * FROM daily_journal
                    WHERE user_id = $1 AND day_number = $2;
                """, user_id, day_number)

                if not journal:
                    logger.error(f"complete_day: journal topilmadi [user_id={user_id}, day={day_number}]")
                    return None

                if journal["is_completed"]:
                    logger.warning(f"complete_day: kun allaqachon yakunlangan [user_id={user_id}, day={day_number}]")
                    return journal

                # 2. Savdolar yig'indisi
                sums = await conn.fetchrow("""
                    SELECT
                        COALESCE(SUM(pnl), 0) AS actual_pnl,
                        COALESCE(SUM(pnl + COALESCE(swap,0) + COALESCE(commission,0)), 0) AS net_pnl
                    FROM trades
                    WHERE user_id = $1 AND day_number = $2;
                """, user_id, day_number)

                net_pnl = float(sums["net_pnl"])
                actual_pnl = float(sums["actual_pnl"])

                # 3. Jami maqsad hisoblash
                total_target = (
                    float(journal["target_profit"]) +
                    float(journal["extra_target"]) +
                    float(journal["carry_over_amount"])
                )

                # 4. Yechish summasi (faqat tasdiqlangan bo'lsa)
                withdrawal = (
                    float(journal["withdrawal_amount"])
                    if journal["is_withdrawal_day"] and journal["withdrawal_confirmed"]
                    else 0.0
                )

                # 5. end_balance hisoblash
                end_balance = float(journal["start_balance"]) + net_pnl - withdrawal

                # 6. Maqsad bajarilmadimi? — rollover
                is_rolled_over = net_pnl < total_target

                # 7. Journalni yangilash
                updated = await conn.fetchrow("""
                    UPDATE daily_journal SET
                        actual_pnl     = $3,
                        net_pnl        = $4,
                        end_balance    = $5,
                        is_completed   = TRUE,
                        is_rolled_over = $6,
                        completed_at   = NOW()
                    WHERE user_id = $1 AND day_number = $2
                    RETURNING *;
                """, user_id, day_number, actual_pnl, net_pnl, end_balance, is_rolled_over)

                return updated
    except Exception as e:
        logger.error(f"complete_day xato [user_id={user_id}, day={day_number}]: {e}")
        raise


async def get_journal_range(
    user_id: int,
    date_from: date,
    date_to: date,
) -> list[Record]:
    """
    Berilgan sana oralig'idagi jurnal yozuvlarini qaytaradi.
    Statistika va grafik uchun ishlatiladi.
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            return await conn.fetch("""
                SELECT * FROM daily_journal
                WHERE user_id = $1
                  AND date >= $2
                  AND date <= $3
                ORDER BY date ASC;
            """, user_id, date_from, date_to)
    except Exception as e:
        logger.error(f"get_journal_range xato [user_id={user_id}]: {e}")
        raise


# ─────────────────────────────────────────────
# 📊 STATS
# ─────────────────────────────────────────────

async def get_stats(user_id: int, date_from: date, date_to: date) -> dict:
    """
    Berilgan davr uchun umumiy statistika hisoblaydi.

    Qaytaradi:
        total_days      — jami kunlar soni
        completed_days  — yakunlangan kunlar
        total_net_pnl   — jami net PnL
        total_target    — jami maqsad
        best_day_pnl    — eng yaxshi kun PnL
        worst_day_pnl   — eng yomon kun PnL
        win_days        — maqsadga erishilgan kunlar
        loss_days       — maqsadga erishilmagan kunlar
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*)                                    AS total_days,
                    COUNT(*) FILTER (WHERE is_completed)        AS completed_days,
                    COALESCE(SUM(net_pnl), 0)                   AS total_net_pnl,
                    COALESCE(SUM(
                        target_profit + extra_target + carry_over_amount
                    ), 0)                                       AS total_target,
                    COALESCE(MAX(net_pnl), 0)                   AS best_day_pnl,
                    COALESCE(MIN(net_pnl), 0)                   AS worst_day_pnl,
                    COUNT(*) FILTER (
                        WHERE is_completed AND NOT is_rolled_over
                    )                                           AS win_days,
                    COUNT(*) FILTER (
                        WHERE is_completed AND is_rolled_over
                    )                                           AS loss_days
                FROM daily_journal
                WHERE user_id = $1
                  AND date >= $2
                  AND date <= $3;
            """, user_id, date_from, date_to)

            return dict(row)
    except Exception as e:
        logger.error(f"get_stats xato [user_id={user_id}]: {e}")
        raise


# ─────────────────────────────────────────────
# 🔔 SCHEDULER
# ─────────────────────────────────────────────

async def finish_strategy(user_id: int) -> None:
    """
    Strategiyani yakunlaydi:
    - settings.is_active = FALSE qiladi
    - start_date ni NULL ga tushiradi (yangi strategiya uchun tayyor)

    ⚠️ Diqqat: Barcha savdo va journal ma'lumotlari saqlanib qoladi.
    Foydalanuvchi yangi strategiya boshlaganda start_date yangilanadi.
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE settings
                SET is_active  = FALSE,
                    start_date = NULL
                WHERE user_id = $1;
            """, user_id)
            logger.info(f"Strategiya yakunlandi [user_id={user_id}]")
    except Exception as e:
        logger.error(f"finish_strategy xato [user_id={user_id}]: {e}")
        raise


async def get_strategy_summary(user_id: int) -> Optional[dict]:
    """
    Tugagan strategiya yakuniy natijalarini qaytaradi.
    Strategiya tugash xabari uchun ishlatiladi.

    Qaytaradi:
        total_days       — jami ish kunlari
        win_days         — maqsadga erishilgan kunlar
        loss_days        — maqsadga erishilmagan kunlar
        win_rate         — maqsad bajarilish foizi
        total_net_pnl    — jami net PnL
        starting_balance — boshlang'ich balans
        final_balance    — oxirgi kun end_balance
        total_withdrawal — jami yechilgan summa
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            settings_row = await conn.fetchrow("""
                SELECT starting_balance FROM settings WHERE user_id = $1;
            """, user_id)

            if not settings_row:
                return None

            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE is_completed)                        AS total_days,
                    COUNT(*) FILTER (WHERE is_completed AND NOT is_rolled_over) AS win_days,
                    COUNT(*) FILTER (WHERE is_completed AND is_rolled_over)     AS loss_days,
                    COALESCE(SUM(net_pnl) FILTER (WHERE is_completed), 0)       AS total_net_pnl,
                    COALESCE(SUM(withdrawal_amount) FILTER (
                        WHERE is_completed AND withdrawal_confirmed
                    ), 0)                                                        AS total_withdrawal
                FROM daily_journal
                WHERE user_id = $1;
            """, user_id)

            # Oxirgi yakunlangan kun balansi
            last_balance_row = await conn.fetchrow("""
                SELECT end_balance FROM daily_journal
                WHERE user_id = $1 AND is_completed = TRUE
                ORDER BY date DESC
                LIMIT 1;
            """, user_id)

            total_days = int(row["total_days"] or 0)
            win_days = int(row["win_days"] or 0)
            win_rate = round((win_days / total_days * 100), 1) if total_days > 0 else 0.0

            return {
                "total_days":       total_days,
                "win_days":         win_days,
                "loss_days":        int(row["loss_days"] or 0),
                "win_rate":         win_rate,
                "total_net_pnl":    float(row["total_net_pnl"] or 0),
                "starting_balance": float(settings_row["starting_balance"] or 0),
                "final_balance":    float(last_balance_row["end_balance"] or 0) if last_balance_row else 0.0,
                "total_withdrawal": float(row["total_withdrawal"] or 0),
            }
    except Exception as e:
        logger.error(f"get_strategy_summary xato [user_id={user_id}]: {e}")
        raise


async def get_all_active_users() -> list[Record]:
    """
    Sozlamalari to'liq kiritilgan (is_active=TRUE) barcha
    foydalanuvchilarni qaytaradi.
    Scheduler eslatmalari uchun ishlatiladi.

    Qaytaradi: users + settings ustunlari (JOIN).
    """
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            return await conn.fetch("""
                SELECT
                    u.id            AS user_id,
                    u.telegram_id,
                    u.username,
                    s.*
                FROM users u
                JOIN settings s ON s.user_id = u.id
                WHERE s.is_active = TRUE;
            """)
    except Exception as e:
        logger.error(f"get_all_active_users xato: {e}")
        raise
