from database.queries import get_all_users_for_reminder_all, get_settings
from utils.calculator import get_current_day, calculate_balance_progression
from utils.logger import logger
from datetime import datetime
import pytz


async def send_daily_reminders(bot):
    try:
        users = await get_all_users_for_reminder_all()
        for user in users:
            telegram_id = user["telegram_id"]
            reminder_time = user["reminder_time"]
            timezone = user.get("timezone") or "Asia/Tashkent"
            try:
                tz = pytz.timezone(timezone)
                local_time = datetime.now(tz).strftime("%H:%M")
                if local_time != reminder_time:
                    continue

                from database.queries import get_user_id
                user_id = await get_user_id(telegram_id)
                if not user_id:
                    continue

                settings = await get_settings(user_id)
                if not settings:
                    continue

                day = get_current_day(settings["start_date"])
                total_days = settings["total_days"]
                if day > total_days:
                    continue

                progression = calculate_balance_progression(settings)
                day_data = progression[day - 1] if day <= len(progression) else None
                if not day_data:
                    continue

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
                logger.info(f"Eslatma yuborildi: {telegram_id}")

            except Exception as e:
                logger.error(f"Eslatma xatosi ({telegram_id}): {e}")

    except Exception as e:
        logger.error(f"send_daily_reminders xatosi: {e}")
