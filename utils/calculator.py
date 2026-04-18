from datetime import datetime, timedelta


def calculate_day_target(balance: float, rate: float, extra: float) -> dict:
    """Kunlik maqsadni hisoblaydi"""
    profit_target = round(balance * rate, 2)
    total_target = round(profit_target + extra, 2)
    return {
        "profit_target": profit_target,
        "extra_target": extra,
        "total_target": total_target
    }


def get_current_day(start_date_str: str) -> int:
    """Bugun strategiyaning necha-kunchi kuni ekanligini qaytaradi"""
    try:
        start = datetime.strptime(start_date_str, "%d.%m.%Y").date()
        today = datetime.now().date()
        delta = (today - start).days + 1
        return max(1, delta)
    except Exception:
        return 1


def is_withdrawal_day(day_number: int, withdrawal_every: int) -> bool:
    """Bu kun yechish kuni ekanligini tekshiradi"""
    return day_number > 0 and day_number % withdrawal_every == 0


def calculate_balance_progression(settings: dict) -> list:
    """Butun strategiya davri uchun balans progressiyasini hisoblaydi"""
    balance = settings["starting_balance"]
    rate = settings["daily_profit_rate"]
    extra = settings.get("extra_target", 0)
    days = settings["total_days"]
    withdrawal = settings.get("withdrawal_amount", 0)
    withdrawal_every = settings.get("withdrawal_every", 7)
    start_date_str = settings.get("start_date", "01.01.2025")

    result = []
    for day in range(1, days + 1):
        profit = round(balance * rate, 2)
        total_target = round(profit + extra, 2)
        is_wday = is_withdrawal_day(day, withdrawal_every) and withdrawal > 0
        end_balance = round(balance + profit, 2)
        withdrawn = round(withdrawal, 2) if is_wday else 0
        final_balance = round(end_balance - withdrawn, 2)

        try:
            start_date = datetime.strptime(start_date_str, "%d.%m.%Y")
            day_date = (start_date + timedelta(days=day - 1)).strftime("%d.%m.%Y")
        except Exception:
            day_date = f"Kun {day}"

        result.append({
            "day": day,
            "date": day_date,
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
    """Strategiya yakuniy natijasini hisoblaydi"""
    progression = calculate_balance_progression(settings)
    total_expected = sum(d["profit_target"] + d["extra_target"] for d in progression)
    total_actual = sum(j.get("actual_pnl", 0) for j in journals)
    total_withdrawn = sum(j.get("withdrawal_amount", 0) for j in journals if j.get("withdrawal_confirmed"))

    last_journal = journals[-1] if journals else None
    final_balance = last_journal.get("end_balance", settings["starting_balance"]) if last_journal else settings["starting_balance"]

    return {
        "total_days": settings["total_days"],
        "completed_days": len([j for j in journals if j.get("is_completed")]),
        "starting_balance": settings["starting_balance"],
        "final_balance": final_balance,
        "total_expected_profit": round(total_expected, 2),
        "total_actual_profit": round(total_actual, 2),
        "total_withdrawn": round(total_withdrawn, 2),
        "performance_pct": round((total_actual / total_expected * 100) if total_expected else 0, 1)
    }
