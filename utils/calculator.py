from datetime import datetime, timedelta


def is_weekend(d) -> bool:
    """Shanba(5) yoki Yakshanba(6) ekanligini tekshiradi"""
    return d.weekday() >= 5


def get_working_days_count(start_date_str: str, total_days: int) -> list:
    """Faqat ish kunlarini (Du-Ju) qaytaradi"""
    try:
        start = datetime.strptime(start_date_str, "%d.%m.%Y").date()
    except Exception:
        from datetime import date
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
        from datetime import date
        today = date.today()
        working_days = get_working_days_count(start_date_str, total_days)
        for i, d in enumerate(working_days):
            if d == today:
                return i + 1
        # Bugun ro'yxatda yo'q (dam olish kuni yoki kelajak)
        # Oxirgi o'tgan ish kunini topamiz
        past = [d for d in working_days if d <= today]
        if past:
            return len(past)
        return 1
    except Exception:
        return 1


def is_withdrawal_day(day_number: int, withdrawal_every: int) -> bool:
    return day_number > 0 and day_number % withdrawal_every == 0


def calculate_balance_progression(settings: dict) -> list:
    """Faqat ish kunlari uchun balans progressiyasi"""
    balance = float(settings["starting_balance"] or 0)
    rate = float(settings["daily_profit_rate"] or 0.20)
    extra = float(settings.get("extra_target") or 0)
    days = int(settings["total_days"] or 7)
    withdrawal = float(settings.get("withdrawal_amount") or 0)
    withdrawal_every = int(settings.get("withdrawal_every") or 7)
    start_date_str = settings.get("start_date", "01.01.2025")

    working_days = get_working_days_count(start_date_str, days)
    result = []

    for i, day_date in enumerate(working_days):
        day_number = i + 1
        profit = round(balance * rate, 2)
        total_target = round(profit + extra, 2)
        is_wday = is_withdrawal_day(day_number, withdrawal_every) and withdrawal > 0
        end_balance = round(balance + profit, 2)
        withdrawn = round(withdrawal, 2) if is_wday else 0
        final_balance = round(end_balance - withdrawn, 2)

        result.append({
            "day": day_number,
            "date": day_date.strftime("%d.%m.%Y"),
            "date_iso": day_date.isoformat(),
            "weekday": day_date.strftime("%A"),
            "start_balance": round(balance, 2),
            "profit_target": profit,
            "extra_target": extra,
            "total_target": total_target,
            "end_balance": end_balance,
            "withdrawal": withdrawn,
            "final_balance": final_balance,
            "is_withdrawal_day": is_wday
        })
        balance = final_balance

    return result


def get_strategy_summary(settings: dict, journals: list) -> dict:
    """Strategiya yakuniy natijasi — faqat ish kunlari"""
    progression = calculate_balance_progression(settings)
    # Faqat ish kunlarini hisobga olamiz
    working_journals = [j for j in journals if not _is_weekend_journal(j)]
    total_expected = sum(d["profit_target"] + d["extra_target"] for d in progression)
    total_actual = sum(float(j.get("actual_pnl") or 0) for j in working_journals)
    total_withdrawn = sum(
        float(j.get("withdrawal_amount") or 0)
        for j in working_journals
        if j.get("withdrawal_confirmed")
    )
    completed = [j for j in working_journals if j.get("is_completed")]
    last_completed = next(
        (j for j in reversed(completed) if j.get("end_balance") is not None), None
    )
    final_balance = (
        float(last_completed["end_balance"])
        if last_completed
        else float(settings["starting_balance"] or 0)
    )

    return {
        "total_days": settings["total_days"],
        "completed_days": len(completed),
        "starting_balance": float(settings["starting_balance"] or 0),
        "final_balance": round(final_balance, 2),
        "total_expected_profit": round(total_expected, 2),
        "total_actual_profit": round(total_actual, 2),
        "total_withdrawn": round(total_withdrawn, 2),
        "performance_pct": round(
            (total_actual / total_expected * 100) if total_expected else 0, 1
        )
    }


def _is_weekend_journal(j: dict) -> bool:
    """Journal yozuvi dam olish kuniga tegishli ekanligini tekshiradi"""
    try:
        from datetime import date
        d = j.get("date")
        if isinstance(d, str):
            from datetime import datetime
            d = datetime.strptime(d, "%Y-%m-%d").date()
        return is_weekend(d)
    except Exception:
        return False
