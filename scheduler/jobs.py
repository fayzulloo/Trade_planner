from database.queries import get_all_users_for_reminder_all, get_settings, get_today_journal
from utils.calculator import get_current_day, calculate_balance_progression
from utils.logger import logger
from datetime import datetime, date
import pytz


async def _get_local_time(timezone: str) -> str:
    try:
        tz = pytz.timezone(timezone or "Asia/Tashkent")
        return datetime.now(tz).strftime("%H:%M")
    except Exception:
        return datetime.utcnow().strftime("%H:%M")


async def send_daily_reminders(bot):
    """Har daqiqa ishga tushadi — ertalabki, kechki eslatma va avtomatik yakunlash"""
    try:
        users = await get_all_users_for_reminder_all()
        for user in users:
            telegram_id = user["telegram_id"]
            timezone = user.get("timezone") or "Asia/Tashkent"
            reminder_time = user.get("reminder_time")
            evening_time = user.get("evening_reminder_time")
            auto_complete_time = user.get("auto_complete_time")

            try:
                local_time = await _get_local_time(timezone)

                from database.queries import get_user_id
                user_id = await get_user_id(telegram_id)
                if not user_id:
                    continue

                settings = await get_settings(user_id)
                if not settings:
                    continue

                from utils.calculator import parse_rest_days, is_today_rest_day
                rest_days = parse_rest_days(settings.get("rest_days") or "6,7")
                day = get_current_day(settings["start_date"], settings["total_days"], rest_days)
                total_days = settings["total_days"]

                # Dam olish kunini tekshirish (custom sozlamalar bilan)
                today = date.today()
                if is_today_rest_day(rest_days):
                    continue

                if day > total_days:
                    continue

                progression = calculate_balance_progression(settings)
                day_data = progression[day - 1] if day <= len(progression) else None
                if not day_data:
                    continue

                # 1. ERTALABKI ESLATMA
                if reminder_time and local_time == reminder_time:
                    await _send_morning_reminder(bot, telegram_id, day, total_days, day_data)

                # 2. KECHKI ESLATMA
                if evening_time and local_time == evening_time:
                    await _send_evening_reminder(bot, telegram_id, user_id, day)

                # 3. AVTOMATIK YAKUNLASH
                if auto_complete_time and local_time == auto_complete_time:
                    await _auto_complete_day(bot, telegram_id, user_id)

            except Exception as e:
                logger.error(f"Foydalanuvchi {telegram_id} uchun job xatosi: {e}")

    except Exception as e:
        logger.error(f"send_daily_reminders xatosi: {e}")


async def _send_morning_reminder(bot, telegram_id: int, day: int,
                                   total_days: int, day_data: dict):
    try:
        msg = (
            f"🌅 <b>Xayrli tong!</b>\n\n"
            f"📅 Bugun {day}-kun / {total_days}\n"
            f"💰 Balans: <b>{day_data['start_balance']}$</b>\n"
            f"🎯 Bugungi maqsad: <b>+{day_data['total_target']}$</b>\n"
        )
        if day_data["is_withdrawal_day"]:
            msg += f"\n⚠️ <b>Bugun yechish kuni!</b> {day_data['withdrawal']}$\n"
        msg += "\n📊 <b>Bugungi reja</b> tugmasini bosing."
        await bot.send_message(telegram_id, msg, parse_mode="HTML")
        logger.info(f"Ertalabki eslatma: {telegram_id}")
    except Exception as e:
        logger.error(f"Ertalabki eslatma xatosi ({telegram_id}): {e}")


async def _send_evening_reminder(bot, telegram_id: int, user_id: int, day: int):
    try:
        journal = await get_today_journal(user_id)
        if journal and journal.get("is_completed"):
            return  # Kun allaqachon yakunlangan

        actual_pnl = float(journal.get("actual_pnl") or 0) if journal else 0
        target = float(journal.get("target_profit") or 0) + float(journal.get("extra_target") or 0) if journal else 0
        remaining = round(target - actual_pnl, 2)
        rem_emoji = "✅" if remaining <= 0 else "⏳"

        msg = (
            f"🌙 <b>Kechki eslatma</b>\n\n"
            f"📅 {day}-kun hali yakunlanmagan.\n\n"
            f"💵 Hozirgi PnL: <b>{'+' if actual_pnl >= 0 else ''}{actual_pnl}$</b>\n"
            f"{rem_emoji} Qoldi: <b>{max(0, remaining)}$</b>\n\n"
            f"Kunni yakunlash uchun <b>📊 Bugungi reja</b> ga kiring."
        )
        await bot.send_message(telegram_id, msg, parse_mode="HTML")
        logger.info(f"Kechki eslatma: {telegram_id}")
    except Exception as e:
        logger.error(f"Kechki eslatma xatosi ({telegram_id}): {e}")


async def _auto_complete_day(bot, telegram_id: int, user_id: int):
    try:
        journal = await get_today_journal(user_id)
        if not journal:
            return
        if journal.get("is_completed"):
            return  # Allaqachon yakunlangan

        from database.queries import complete_day
        completed = await complete_day(user_id)
        end_balance = float(completed.get("end_balance") or 0)
        actual_pnl = float(completed.get("actual_pnl") or 0)
        sign = "+" if actual_pnl >= 0 else ""

        msg = (
            f"🔄 <b>Kun avtomatik yakunlandi</b>\n\n"
            f"💰 Yakuniy balans: <b>{end_balance}$</b>\n"
            f"📈 Bugungi PnL: <b>{sign}{actual_pnl}$</b>"
        )
        await bot.send_message(telegram_id, msg, parse_mode="HTML")
        logger.info(f"Avtomatik yakunlash: {telegram_id}")
    except Exception as e:
        logger.error(f"Avtomatik yakunlash xatosi ({telegram_id}): {e}")
