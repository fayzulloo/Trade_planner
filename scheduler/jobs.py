"""
Scheduler ishlari (jobs).
Har bir job alohida funksiya sifatida yozilgan.
"""

import logging
from datetime import date, timedelta

from database.queries import (
    get_all_active_users,
    get_settings,
    get_today_journal,
    create_journal_day,
    complete_day,
    get_journal_range,
    get_strategy_summary,
    finish_strategy,
)
from utils.calculator import (
    get_current_date,
    parse_start_date,
    get_day_number,
    is_rest_day,
    is_withdrawal_day,
    is_strategy_finished,
    calc_target_profit,
    calc_total_target,
    calc_remaining,
    format_money,
)

logger = logging.getLogger(__name__)


async def job_create_daily_journals(bot) -> None:
    """
    Har kuni 00:01 da ishlaydi.
    Barcha active userlar uchun yangi kun journali yaratadi.
    carry_over create_journal_day ichida avtomatik hisoblanadi.
    """
    logger.info("job_create_daily_journals boshlandi.")
    users = await get_all_active_users()

    for user in users:
        try:
            user_id = user["user_id"]
            settings = dict(user)
            timezone = settings.get("timezone", "Asia/Tashkent")
            today = get_current_date(timezone)

            # Dam olish kunimi?
            if is_rest_day(today, settings.get("rest_days", "")):
                continue

            # Strategiya tugaganmi?
            start_date_str = settings.get("start_date")
            if not start_date_str:
                continue

            start_date = parse_start_date(start_date_str)
            if not start_date:
                continue

            total_days = settings.get("total_days") or 0

            if is_strategy_finished(start_date, today, settings.get("rest_days", ""), total_days):
                # Strategiya tugagan — xabar yuborish va yakunlash
                await _handle_strategy_finished(bot, user_id, settings)
                continue

            day_number = get_day_number(
                start_date, today,
                settings.get("rest_days", ""),
                total_days,
            )
            if not day_number:
                continue

            # Allaqachon yaratilganmi?
            existing = await get_today_journal(user_id, today)
            if existing:
                continue

            # Oldingi kun balansi
            start_balance = float(settings.get("starting_balance") or 0)
            prev_journals = await get_journal_range(
                user_id,
                start_date,
                today - timedelta(days=1),
            )
            if prev_journals:
                last = prev_journals[-1]
                if last["end_balance"]:
                    start_balance = float(last["end_balance"])

            target_profit = calc_target_profit(
                start_balance,
                float(settings.get("daily_profit_rate") or 0.1),
            )

            withdrawal_every = settings.get("withdrawal_every") or 7
            _is_wd = is_withdrawal_day(day_number, withdrawal_every)

            await create_journal_day(
                user_id=user_id,
                day_number=day_number,
                today=today,
                start_balance=start_balance,
                target_profit=target_profit,
                extra_target=float(settings.get("extra_target") or 0),
                withdrawal_amount=float(settings.get("withdrawal_amount") or 0) if _is_wd else 0,
                is_withdrawal_day=_is_wd,
            )

            logger.info(f"Journal yaratildi [user_id={user_id}, day={day_number}, date={today}]")

        except Exception as e:
            logger.error(f"job_create_daily_journals xato [user_id={user.get('user_id')}]: {e}")

    logger.info("job_create_daily_journals yakunlandi.")


async def job_morning_reminder(bot) -> None:
    """
    Har daqiqa ishlaydi.
    Har user o'z reminder_time va timezone ini tekshiradi.
    Mos kelsa — ertalabki eslatma yuboradi.
    """
    from utils.calculator import get_current_datetime
    users = await get_all_active_users()

    for user in users:
        try:
            user_id = user["user_id"]
            telegram_id = user["telegram_id"]
            settings = dict(user)
            timezone = settings.get("timezone", "Asia/Tashkent")

            # Foydalanuvchi vaqtini tekshirish
            reminder_time = settings.get("reminder_time", "08:00")
            parsed = parse_time_str(reminder_time)
            if not parsed:
                continue

            now = get_current_datetime(timezone)
            if not (now.hour == parsed[0] and now.minute == parsed[1]):
                continue

            today = now.date()

            # Dam olish kunimi?
            if is_rest_day(today, settings.get("rest_days", "")):
                await bot.send_message(
                    telegram_id,
                    "😴 Bugun dam olish kuni.\nYaxshi dam oling!",
                )
                continue

            journal = await get_today_journal(user_id, today)
            if not journal:
                continue

            start_date_str = settings.get("start_date")
            if not start_date_str:
                continue
            start_date = parse_start_date(start_date_str)
            if not start_date:
                continue

            day_number = get_day_number(
                start_date, today,
                settings.get("rest_days", ""),
                settings.get("total_days") or 0,
            )
            if not day_number:
                continue

            total_target = calc_total_target(
                float(journal["target_profit"]),
                float(journal["extra_target"]),
                float(journal["carry_over_amount"]),
            )

            carry_line = ""
            if float(journal["carry_over_amount"]) > 0:
                carry_line = f"\n⚠️ Rollover: +{format_money(float(journal['carry_over_amount']))}"

            await bot.send_message(
                telegram_id,
                f"📊 <b>Bugungi reja</b>\n"
                f"{'─' * 18}\n"
                f"📅 {day_number}-kun / {settings.get('total_days', '?')}\n"
                f"💰 Balans: {format_money(float(journal['start_balance']))}\n"
                f"🎯 Bugungi maqsad: {format_money(total_target)}"
                f"{carry_line}\n"
                f"⏰ Omad!",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"job_morning_reminder xato [user_id={user.get('user_id')}]: {e}")

    logger.info("job_morning_reminder tekshiruvi yakunlandi.")


async def job_evening_reminder(bot) -> None:
    """
    Har daqiqa ishlaydi.
    Har user o'z evening_reminder_time ini tekshiradi.
    Mos kelsa — kechki eslatma yuboradi.
    """
    from utils.calculator import get_current_datetime
    users = await get_all_active_users()

    for user in users:
        try:
            user_id = user["user_id"]
            telegram_id = user["telegram_id"]
            settings = dict(user)

            # Kechki eslatma o'chirilgan bo'lsa — o'tkazib yuborish
            evening_time = settings.get("evening_reminder_time")
            if not evening_time:
                continue

            parsed = parse_time_str(evening_time)
            if not parsed:
                continue

            timezone = settings.get("timezone", "Asia/Tashkent")
            now = get_current_datetime(timezone)

            if not (now.hour == parsed[0] and now.minute == parsed[1]):
                continue

            today = now.date()

            if is_rest_day(today, settings.get("rest_days", "")):
                continue

            journal = await get_today_journal(user_id, today)
            if not journal or journal["is_completed"]:
                continue

            total_target = calc_total_target(
                float(journal["target_profit"]),
                float(journal["extra_target"]),
                float(journal["carry_over_amount"]),
            )
            current_pnl = float(journal["actual_pnl"] or 0)
            remaining = calc_remaining(total_target, current_pnl)
            pnl_icon = "🟢" if current_pnl >= 0 else "🔴"

            await bot.send_message(
                telegram_id,
                f"🌙 <b>Kun yakunlanmoqda</b>\n"
                f"{'─' * 18}\n"
                f"🎯 Maqsad: {format_money(total_target)}\n"
                f"{pnl_icon} PnL: {format_money(current_pnl)}\n"
                f"⏳ Qoldi: {format_money(remaining)}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"job_evening_reminder xato [user_id={user.get('user_id')}]: {e}")

    logger.info("job_evening_reminder tekshiruvi yakunlandi.")


async def job_auto_complete(bot) -> None:
    """
    Har daqiqa ishlaydi.
    Har user o'z auto_complete_time ini tekshiradi.
    Mos kelsa — yakunlanmagan kunni avtomatik yakunlaydi.

    ⚠️ Diqqat: Bu majburiy job — kun har doim yakunlanishi kerak.
    """
    from utils.calculator import get_current_datetime
    users = await get_all_active_users()

    for user in users:
        try:
            user_id = user["user_id"]
            telegram_id = user["telegram_id"]
            settings = dict(user)

            auto_time = settings.get("auto_complete_time", "23:30")
            parsed = parse_time_str(auto_time)
            if not parsed:
                continue

            timezone = settings.get("timezone", "Asia/Tashkent")
            now = get_current_datetime(timezone)

            if not (now.hour == parsed[0] and now.minute == parsed[1]):
                continue

            today = now.date()

            if is_rest_day(today, settings.get("rest_days", "")):
                continue

            journal = await get_today_journal(user_id, today)
            if not journal or journal["is_completed"]:
                continue

            updated = await complete_day(user_id, journal["day_number"])
            if not updated:
                continue

            net_pnl = float(updated["net_pnl"] or 0)
            end_balance = float(updated["end_balance"] or 0)
            icon = "🟢" if not updated["is_rolled_over"] else "🔴"

            rollover_text = ""
            if updated["is_rolled_over"]:
                total_target = calc_total_target(
                    float(updated["target_profit"]),
                    float(updated["extra_target"]),
                    float(updated["carry_over_amount"]),
                )
                missing = calc_remaining(total_target, net_pnl)
                rollover_text = f"\n⚠️ {format_money(missing)} keyingi kunga o'tadi."

            await bot.send_message(
                telegram_id,
                f"{icon} <b>Kun avtomatik yakunlandi</b>\n\n"
                f"💰 Net PnL: {format_money(net_pnl)}\n"
                f"🏦 Yangi balans: {format_money(end_balance)}"
                f"{rollover_text}",
                parse_mode="HTML",
            )

            logger.info(f"Auto-complete [user_id={user_id}, day={journal['day_number']}]")

        except Exception as e:
            logger.error(f"job_auto_complete xato [user_id={user.get('user_id')}]: {e}")

    logger.info("job_auto_complete tekshiruvi yakunlandi.")


async def _handle_strategy_finished(bot, user_id: int, settings: dict) -> None:
    """
    Strategiya tugaganda xabar yuboradi va finish_strategy chaqiradi.
    """
    try:
        from handlers.keyboards import strategy_finished_kb
        summary = await get_strategy_summary(user_id)
        await finish_strategy(user_id)

        if not summary:
            return

        profit = summary["final_balance"] - summary["starting_balance"]
        telegram_id = settings["telegram_id"]

        await bot.send_message(
            telegram_id,
            f"🏁 <b>Strategiya yakunlandi!</b>\n"
            f"{'─' * 20}\n"
            f"📅 Jami kunlar: {summary['total_days']}\n"
            f"✅ Win rate: {summary['win_rate']}%\n\n"
            f"💰 Boshlang'ich: {format_money(summary['starting_balance'])}\n"
            f"🏦 Yakuniy: {format_money(summary['final_balance'])}\n"
            f"📈 Jami foyda: {format_money(profit)}\n"
            f"💸 Jami yechildi: {format_money(summary['total_withdrawal'])}",
            reply_markup=strategy_finished_kb(),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"_handle_strategy_finished xato [user_id={user_id}]: {e}")
