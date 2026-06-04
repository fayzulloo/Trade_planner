"""
Trading hisob-kitoblari uchun yordamchi funksiyalar.
Barcha moliyaviy hisob-kitoblar shu yerda markazlashgan.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional
import pytz

from config import DEFAULT_TIMEZONE

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 📅 SANA VA KUN HISOBLASH
# ─────────────────────────────────────────────

def get_current_date(timezone: str = DEFAULT_TIMEZONE) -> date:
    """
    Foydalanuvchi timezone bo'yicha hozirgi sanani qaytaradi.
    """
    try:
        tz = pytz.timezone(timezone)
        return datetime.now(tz).date()
    except Exception as e:
        logger.error(f"get_current_date xato [tz={timezone}]: {e}")
        return datetime.now().date()


def get_current_datetime(timezone: str = DEFAULT_TIMEZONE) -> datetime:
    """
    Foydalanuvchi timezone bo'yicha hozirgi datetime qaytaradi.
    """
    try:
        tz = pytz.timezone(timezone)
        return datetime.now(tz)
    except Exception as e:
        logger.error(f"get_current_datetime xato [tz={timezone}]: {e}")
        return datetime.now()


def parse_start_date(start_date_str: str) -> Optional[date]:
    """
    Sozlamadagi sana stringini date ga o'giradi.
    Format: DD.MM.YYYY
    """
    try:
        return datetime.strptime(start_date_str, "%d.%m.%Y").date()
    except Exception as e:
        logger.error(f"parse_start_date xato [{start_date_str}]: {e}")
        return None


def get_day_number(
    start_date: date,
    today: date,
    rest_days: str = "",
    total_days: int = 0,
) -> Optional[int]:
    """
    Bugungi strategiya kun raqamini hisoblaydi.
    Dam olish kunlari hisobga olinmaydi.

    Parametrlar:
        start_date — strategiya boshlanish sanasi
        today      — bugungi sana
        rest_days  — dam olish kunlari ("6,7" formatida, 1=Yakshanba...7=Shanba)
        total_days — strategiya davri (kun). 0 bo'lsa limit yo'q.

    Qaytaradi:
        Kun raqami (1 dan boshlab)
        None — dam olish kuni bo'lsa
        None — strategiya tugagan bo'lsa (day_number > total_days)
        None — strategiya boshlanmagan bo'lsa (today < start_date)

    ⚠️ Diqqat: Python weekday() 0=Dushanba...6=Yakshanba
    Bizning format:  1=Yakshanba, 2=Dushanba ... 7=Shanba
    Konversiya: (weekday + 2) % 7 or 7
    """
    try:
        if today < start_date:
            return None

        # Dam olish kunlari ro'yxati
        rest_list = []
        if rest_days:
            rest_list = [int(d.strip()) for d in rest_days.split(",") if d.strip().isdigit()]

        # Python weekday → bizning format (1=Yakshanba...7=Shanba)
        def to_our_weekday(d: date) -> int:
            # Python: 0=Mon, 1=Tue, ..., 6=Sun
            # Bizniki: 1=Sun, 2=Mon, ..., 7=Sat
            return (d.weekday() + 2) % 7 or 7

        # Bugun dam olish kunimi?
        if to_our_weekday(today) in rest_list:
            return None

        # Boshlanish sanasidan bugungacha ish kunlarini sanash
        day_count = 0
        current = start_date
        while current <= today:
            if to_our_weekday(current) not in rest_list:
                day_count += 1
            current += timedelta(days=1)

        # ⚠️ Strategiya tugaganmi?
        if total_days > 0 and day_count > total_days:
            return None

        return day_count
    except Exception as e:
        logger.error(f"get_day_number xato: {e}")
        return None


def is_strategy_finished(
    start_date: date,
    today: date,
    rest_days: str = "",
    total_days: int = 0,
) -> bool:
    """
    Strategiya davri tugaganini tekshiradi.

    Qaytaradi:
        True  — strategiya tugagan (day_number > total_days)
        False — hali davom etmoqda yoki boshlanmagan
    """
    try:
        if total_days <= 0:
            return False
        if today < start_date:
            return False

        rest_list = []
        if rest_days:
            rest_list = [int(d.strip()) for d in rest_days.split(",") if d.strip().isdigit()]

        def to_our_weekday(d: date) -> int:
            return (d.weekday() + 2) % 7 or 7

        day_count = 0
        current = start_date
        while current <= today:
            if to_our_weekday(current) not in rest_list:
                day_count += 1
            current += timedelta(days=1)

        return day_count > total_days
    except Exception as e:
        logger.error(f"is_strategy_finished xato: {e}")
        return False


def is_rest_day(today: date, rest_days: str = "") -> bool:
    """
    Bugun dam olish kunimi?
    """
    try:
        if not rest_days:
            return False
        rest_list = [int(d.strip()) for d in rest_days.split(",") if d.strip().isdigit()]

        def to_our_weekday(d: date) -> int:
            return (d.weekday() + 2) % 7 or 7

        return to_our_weekday(today) in rest_list
    except Exception as e:
        logger.error(f"is_rest_day xato: {e}")
        return False


def is_withdrawal_day(day_number: int, withdrawal_every: int) -> bool:
    """
    Bu kun yechish kunimi?
    withdrawal_every — har necha kunda yechish.

    Misol: withdrawal_every=7 bo'lsa 7, 14, 21... kunlarda True
    ⚠️ Diqqat: 1-kun hech qachon yechish kuni emas
    """
    if day_number <= 1 or withdrawal_every <= 0:
        return False
    return day_number % withdrawal_every == 0


# ─────────────────────────────────────────────
# 💰 BALANS VA MAQSAD HISOBLASH
# ─────────────────────────────────────────────

def calc_target_profit(balance: float, daily_rate: float) -> float:
    """
    Kunlik foiz asosida maqsad foyda hisoblaydi.

    Parametrlar:
        balance    — kun boshidagi balans
        daily_rate — kunlik foiz (0.10 = 10%)

    Qaytaradi: maqsad foyda summasi ($)
    """
    try:
        return round(balance * daily_rate, 2)
    except Exception as e:
        logger.error(f"calc_target_profit xato: {e}")
        return 0.0


def calc_total_target(
    target_profit: float,
    extra_target: float = 0,
    carry_over: float = 0,
) -> float:
    """
    Kunning jami maqsadini hisoblaydi.
    total_target = target_profit + extra_target + carry_over_amount
    """
    return round(target_profit + extra_target + carry_over, 2)


def calc_planned_balance(
    starting_balance: float,
    daily_rate: float,
    day_number: int,
    extra_target: float = 0,
    withdrawal_amount: float = 0,
    withdrawal_every: int = 0,
) -> float:
    """
    N-kun oxiridagi rejalangan balansni hisoblaydi.

    Formula (har kun uchun):
        profit          = balance * daily_rate
        ending_balance  = balance + profit + extra_target
        yechish kuni:   balance = ending_balance - withdrawal_amount
        oddiy kun:      balance = ending_balance

    Parametrlar:
        starting_balance  — boshlang'ich balans
        daily_rate        — kunlik foiz (0.10 = 10%)
        day_number        — necha kunlik hisob
        extra_target      — qo'shimcha kunlik maqsad ($)
        withdrawal_amount — yechish summasi ($)
        withdrawal_every  — har necha kunda yechish (0 = yechish yo'q)
    """
    try:
        balance = starting_balance
        for day in range(1, day_number + 1):
            profit = balance * daily_rate
            ending_balance = balance + profit + extra_target

            # Yechish kuni
            if withdrawal_every > 0 and withdrawal_amount > 0 and day % withdrawal_every == 0:
                balance = ending_balance - withdrawal_amount
            else:
                balance = ending_balance

        return round(balance, 2)
    except Exception as e:
        logger.error(f"calc_planned_balance xato: {e}")
        return starting_balance


def calc_end_balance(
    start_balance: float,
    net_pnl: float,
    withdrawal: float = 0,
) -> float:
    """
    Kun oxiridagi haqiqiy balansni hisoblaydi.
    end_balance = start_balance + net_pnl - withdrawal
    """
    return round(start_balance + net_pnl - withdrawal, 2)


def calc_remaining(total_target: float, current_pnl: float) -> float:
    """
    Maqsadga yetish uchun qolgan summani hisoblaydi.
    Manfiy bo'lsa — maqsad oshib ketgan.
    """
    return round(total_target - current_pnl, 2)


def calc_progress_percent(current_pnl: float, total_target: float) -> float:
    """
    Maqsad bajarilish foizini hisoblaydi.
    Maksimal 100% (oshiqcha ko'rsatilmaydi).
    """
    try:
        if total_target <= 0:
            return 100.0
        percent = (current_pnl / total_target) * 100
        return round(min(percent, 100.0), 1)
    except Exception as e:
        logger.error(f"calc_progress_percent xato: {e}")
        return 0.0


def calc_strategy_progress(
    starting_balance: float,
    current_balance: float,
    daily_rate: float,
    total_days: int,
    current_day: int,
    extra_target: float = 0,
) -> dict:
    """
    Strategiya davri umumiy progress ma'lumotlarini hisoblaydi.

    Qaytaradi:
        planned_final   — strategiya oxiridagi rejalangan balans
        planned_current — hozirgi kun rejalangan balans
        actual_balance  — haqiqiy hozirgi balans
        progress_days   — kun bo'yicha progress foizi
        progress_balance— balans bo'yicha progress foizi
        difference      — haqiqiy vs rejalangan farq
    """
    try:
        planned_final = calc_planned_balance(
            starting_balance, daily_rate, total_days, extra_target
        )
        planned_current = calc_planned_balance(
            starting_balance, daily_rate, current_day, extra_target
        )
        difference = round(current_balance - planned_current, 2)
        progress_days = round((current_day / total_days) * 100, 1) if total_days > 0 else 0
        progress_balance = round(
            ((current_balance - starting_balance) /
             (planned_final - starting_balance)) * 100, 1
        ) if planned_final > starting_balance else 0

        return {
            "planned_final":    planned_final,
            "planned_current":  planned_current,
            "actual_balance":   current_balance,
            "progress_days":    progress_days,
            "progress_balance": progress_balance,
            "difference":       difference,
        }
    except Exception as e:
        logger.error(f"calc_strategy_progress xato: {e}")
        return {}


# ─────────────────────────────────────────────
# 📊 STATISTIKA HISOBLASH
# ─────────────────────────────────────────────

def calc_win_rate(win_days: int, total_completed: int) -> float:
    """
    Win rate foizini hisoblaydi.
    win_days / total_completed * 100
    """
    try:
        if total_completed <= 0:
            return 0.0
        return round((win_days / total_completed) * 100, 1)
    except Exception as e:
        logger.error(f"calc_win_rate xato: {e}")
        return 0.0


def calc_average_pnl(total_pnl: float, total_days: int) -> float:
    """
    Kunlik o'rtacha PnL hisoblaydi.
    """
    try:
        if total_days <= 0:
            return 0.0
        return round(total_pnl / total_days, 2)
    except Exception as e:
        logger.error(f"calc_average_pnl xato: {e}")
        return 0.0


# ─────────────────────────────────────────────
# 🕐 VAQT YORDAMCHILARI
# ─────────────────────────────────────────────

def parse_time_str(time_str: str) -> Optional[tuple[int, int]]:
    """
    "HH:MM" formatdagi vaqtni (hour, minute) ga o'giradi.
    Noto'g'ri format bo'lsa None qaytaradi.
    """
    try:
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            return None
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return hour, minute
    except Exception:
        return None


def format_money(amount: float) -> str:
    """
    Pul summasini chiroyli formatda ko'rsatadi.
    Misol: 1234.5 → "+1,234.50$" yoki "-234.50$"
    """
    try:
        sign = "+" if amount >= 0 else ""
        return f"{sign}{amount:,.2f}$"
    except Exception:
        return f"{amount}$"


def format_date(d: date) -> str:
    """
    Sanani DD.MM.YYYY formatida qaytaradi.
    """
    return d.strftime("%d.%m.%Y")
