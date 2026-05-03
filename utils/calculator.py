from datetime import datetime, timedelta, date


def parse_rest_days(rest_days_str: str) -> set:
    """
    Rest days stringini set ga o'tkazadi.
    Format: "6,7" (6=shanba, 7=yakshanba ISO weekday)
    Python weekday(): 0=dushanba ... 6=yakshanba
    ISO weekday(): 1=dushanba ... 7=yakshanba
    """
    result = set()
    if not rest_days_str:
        return result
    for d in rest_days_str.split(","):
        d = d.strip()
        if d.isdigit():
            iso_day = int(d)
            # ISO 1-7 → Python 0-6
            result.add(iso_day - 1)
    return result


def is_rest_day(d, rest_days: set) -> bool:
    """Berilgan kun dam olish kunimi"""
    return d.weekday() in rest_days


def get_working_days_list(start_date_str: str, total_days: int,
                           rest_days: set = None) -> list:
    """
    Ish kunlari ro'yxatini qaytaradi.
    rest_days — Python weekday() formatida (0=dushanba, 6=yakshanba)
    """
    if rest_days is None:
        rest_days = {5, 6}  # default: shanba, yakshanba
    try:
        start = datetime.strptime(start_date_str, "%d.%m.%Y").date()
    except Exception:
        start = date.today()

    working_days = []
    current = start
    while len(working_days) < total_days:
        if not is_rest_day(current, rest_days):
            working_days.append(current)
        current += timedelta(days=1)
    return working_days


def get_current_day(start_date_str: str, total_days: int,
                     rest_days: set = None) -> int:
    """
    Bugun strategiyaning necha-kunchi ish kuni ekanligini qaytaradi.

    FIX #1: total_days endi majburiy parametr — 999 hardcode olib tashlandi.
    Strategiya tugagan bo'lsa total_days qaytariladi (oxirgi kun).
    Strategiya boshlanmagan bo'lsa 0 qaytariladi.
    """
    if rest_days is None:
        rest_days = {5, 6}
    try:
        today = date.today()
        working_days = get_working_days_list(start_date_str, total_days, rest_days)

        # Bugun ro'yxatda bormi — to'g'ridan-to'g'ri topamiz
        for i, d in enumerate(working_days):
            if d == today:
                return i + 1

        # Bugun ish kuni emas (dam olish kuni) yoki strategiya tugagan
        past = [d for d in working_days if d < today]
        if not past:
            return 0  # Strategiya hali boshlanmagan

        # Strategiya tugagan bo'lsa — oxirgi kun raqamini qaytaramiz
        return min(len(past), total_days)
    except Exception:
        return 1


def is_today_rest_day(rest_days: set = None) -> bool:
    """Bugun dam olish kunimi"""
    if rest_days is None:
        rest_days = {5, 6}
    return date.today().weekday() in rest_days


def is_withdrawal_day(day_number: int, withdrawal_every: int) -> bool:
    """
    FIX #4: withdrawal_every=1 bo'lsa har kuni chiqariladi — bu noto'g'ri.
    Minimal chegara 2 kun qo'yildi.
    """
    return withdrawal_every >= 2 and day_number > 0 and day_number % withdrawal_every == 0


def get_real_balance(starting_balance: float, journals: list) -> float:
    """
    Haqiqiy joriy balans:
    boshlang'ich + Σ(net_pnl) barcha yakunlangan kunlar uchun.

    FIX #3: actual_pnl o'rniga net_pnl ishlatiladi — swap va commission
    ni ham o'z ichiga oladi. net_pnl mavjud bo'lmasa actual_pnl fallback.
    """
    total = float(starting_balance or 0)
    for j in journals:
        if j.get("is_completed"):
            # net_pnl = actual_pnl + swap + commission (trades dan hisoblangan)
            net_pnl = j.get("net_pnl")
            if net_pnl is not None:
                total += float(net_pnl)
            else:
                # Eski journal yozuvlari uchun fallback
                total += float(j.get("actual_pnl") or 0)
    return round(total, 2)


def calculate_balance_progression(settings: dict, journals: list = None) -> list:
    """
    Ish kunlari uchun balans progressiyasi.
    journals berilsa — rollover va haqiqiy balans hisobga olinadi.

    FIX #2: carry_over endi keyingi kunning boshlang'ich balansiga qo'shiladi.
    FIX #5: is_rolled flag balans hisob-kitobida ishlatiladi.
    """
    balance = float(settings.get("starting_balance") or 0)
    rate = float(settings.get("daily_profit_rate") or 0.20)
    extra = float(settings.get("extra_target") or 0)
    days = int(settings.get("total_days") or 7)
    withdrawal = float(settings.get("withdrawal_amount") or 0)
    withdrawal_every = int(settings.get("withdrawal_every") or 7)
    start_date_str = settings.get("start_date") or "01.01.2025"
    rest_days = parse_rest_days(settings.get("rest_days") or "6,7")

    working_days = get_working_days_list(start_date_str, days, rest_days)

    # Journals dan rollover ma'lumotlarini olish
    journal_map = {}
    if journals:
        for j in journals:
            journal_map[int(j.get("day_number", 0))] = j

    result = []
    pending_carry_over = 0.0  # Oldingi kundan ko'chgan rollover summasi

    for i, day_date in enumerate(working_days):
        day_number = i + 1

        # FIX #2 & #5: carry_over joriy kun uchun journal dan olinadi,
        # lekin u keyingi kunning balansiga ta'sir qilishi kerak.
        # pending_carry_over — oldingi kunda is_rolled=True bo'lgan summa.
        carry_over = 0.0
        is_rolled = False
        if day_number in journal_map:
            j = journal_map[day_number]
            carry_over = float(j.get("carry_over_amount") or 0)
            is_rolled = bool(j.get("is_rolled_over"))

        # FIX #2: Oldingi kundan ko'chgan carry_over ni joriy balansga qo'shamiz
        effective_balance = round(balance + pending_carry_over, 2)

        profit = round(effective_balance * rate, 2)
        total_target = round(profit + extra + carry_over, 2)
        is_wday = is_withdrawal_day(day_number, withdrawal_every) and withdrawal > 0
        end_balance = round(effective_balance + profit, 2)
        withdrawn = round(withdrawal, 2) if is_wday else 0.0
        final_balance = round(end_balance - withdrawn, 2)

        result.append({
            "day": day_number,
            "date": day_date.strftime("%d.%m.%Y"),
            "date_iso": day_date.isoformat(),
            "start_balance": effective_balance,
            "profit_target": profit,
            "extra_target": extra,
            "carry_over": carry_over,
            "total_target": total_target,
            "end_balance": end_balance,
            "withdrawal": withdrawn,
            "final_balance": final_balance,
            "is_withdrawal_day": is_wday,
            "is_rolled_over": is_rolled,
        })

        balance = final_balance
        # FIX #5: Keyingi kun uchun carry_over ni saqlаymiz
        pending_carry_over = carry_over if is_rolled else 0.0

    return result


def get_strategy_summary(settings: dict, journals: list) -> dict:
    """Strategiya yakuniy natijasi"""
    progression = calculate_balance_progression(settings, journals)
    total_expected = sum(d["total_target"] for d in progression)

    # FIX #3: net_pnl ishlatiladi (swap + commission bilan birga)
    total_actual = sum(
        float(j.get("net_pnl") if j.get("net_pnl") is not None else j.get("actual_pnl") or 0)
        for j in journals
    )
    total_withdrawn = sum(
        float(j.get("withdrawal_amount") or 0)
        for j in journals
        if j.get("withdrawal_confirmed")
    )
    completed = [j for j in journals if j.get("is_completed")]
    real_balance = get_real_balance(
        settings.get("starting_balance", 0), journals
    )

    return {
        "total_days": int(settings.get("total_days") or 0),
        "completed_days": len(completed),
        "starting_balance": float(settings.get("starting_balance") or 0),
        "real_balance": real_balance,
        "total_expected_profit": round(total_expected, 2),
        "total_actual_profit": round(total_actual, 2),
        "total_withdrawn": round(total_withdrawn, 2),
        "performance_pct": round(
            (total_actual / total_expected * 100) if total_expected else 0, 1
        ),
    }
