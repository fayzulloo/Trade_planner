from datetime import datetime, timedelta, date


def is_weekend(d) -> bool:
    """Shanba(6) yoki Yakshanba(0) ekanligini tekshiradi — PostgreSQL DOW: 0=yakshanba, 6=shanba"""
    return d.weekday() >= 5


def get_working_days_list(start_date_str: str, total_days: int) -> list:
    """Faqat ish kunlari (Du-Ju) ro'yxatini qaytaradi"""
    try:
        start = datetime.strptime(start_date_str, "%d.%m.%Y").date()
    except Exception:
        start = date.today()

    working_days = []
    current = start
    while len(working_days) < total_days:
        if not is_weekend(current):
            working_days.append(current)
        current += timedelta(days=1)
    return working_days


def get_current_day(start_date_str: str, total_days: int = 999) -> int:
    """Bugun strategiyaning necha-kunchi ish kuni ekanligini qaytaradi"""
    try:
        today = date.today()
        working_days = get_working_days_list(start_date_str, total_days)
        for i, d in enumerate(working_days):
            if d == today:
                return i + 1
        # Dam olish kuni yoki tugagan — oxirgi o'tgan ish kunini qaytaramiz
        past = [d for d in working_days if d <= today]
        return len(past) if past else 1
    except Exception:
        return 1


def is_withdrawal_day(day_number: int, withdrawal_every: int) -> bool:
    return withdrawal_every > 0 and day_number > 0 and day_number % withdrawal_every == 0


def calculate_balance_progression(settings: dict) -> list:
    """
    Faqat ish kunlari uchun balans progressiyasi.
    Yechish summasi to'g'ri hisoblanadi: yechish kuni
    yakuniy balansdan ayriladi va keyingi kun shu balansdan boshlanadi.
    """
    balance = float(settings.get("starting_balance") or 0)
    rate = float(settings.get("daily_profit_rate") or 0.20)
    extra = float(settings.get("extra_target") or 0)
    days = int(settings.get("total_days") or 7)
    withdrawal = float(settings.get("withdrawal_amount") or 0)
    withdrawal_every = int(settings.get("withdrawal_every") or 7)
    start_date_str = settings.get("start_date") or "01.01.2025"

    working_days = get_working_days_list(start_date_str, days)
    result = []

    for i, day_date in enumerate(working_days):
        day_number = i + 1
        profit = round(balance * rate, 2)
        total_target = round(profit + extra, 2)
        is_wday = is_withdrawal_day(day_number, withdrawal_every) and withdrawal > 0

        # Kun oxirida balans: boshlang'ich + foyda
        end_balance = round(balance + profit, 2)

        # Yechish bo'lsa — ayriladi
        withdrawn = round(withdrawal, 2) if is_wday else 0.0
        final_balance = round(end_balance - withdrawn, 2)

        result.append({
            "day": day_number,
            "date": day_date.strftime("%d.%m.%Y"),
            "date_iso": day_date.isoformat(),
            "start_balance": round(balance, 2),
            "profit_target": profit,
            "extra_target": extra,
            "total_target": total_target,
            "end_balance": end_balance,
            "withdrawal": withdrawn,
            "final_balance": final_balance,
            "is_withdrawal_day": is_wday,
        })

        # Keyingi kun yechishdan keyingi balansdan boshlanadi
        balance = final_balance

    return result


def get_strategy_summary(settings: dict, journals: list) -> dict:
    """Strategiya yakuniy natijasi — faqat ish kunlari"""
    progression = calculate_balance_progression(settings)
    total_expected = sum(d["profit_target"] + d["extra_target"] for d in progression)
    total_actual = sum(float(j.get("actual_pnl") or 0) for j in journals)
    total_withdrawn = sum(
        float(j.get("withdrawal_amount") or 0)
        for j in journals
        if j.get("withdrawal_confirmed")
    )
    completed = [j for j in journals if j.get("is_completed")]
    last_completed = next(
        (j for j in reversed(completed) if j.get("end_balance") is not None), None
    )
    final_balance = (
        float(last_completed["end_balance"])
        if last_completed
        else float(settings.get("starting_balance") or 0)
    )

    return {
        "total_days": int(settings.get("total_days") or 0),
        "completed_days": len(completed),
        "starting_balance": float(settings.get("starting_balance") or 0),
        "final_balance": round(final_balance, 2),
        "total_expected_profit": round(total_expected, 2),
        "total_actual_profit": round(total_actual, 2),
        "total_withdrawn": round(total_withdrawn, 2),
        "performance_pct": round(
            (total_actual / total_expected * 100) if total_expected else 0, 1
        ),
    }
