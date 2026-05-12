"""
Bugungi reja handlerlari.
Kun ma'lumotlarini ko'rsatadi, yakunlash va yechish logikasi.
"""

import logging
from datetime import date as date_type

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from config import WEBAPP_URL
from database.queries import (
    get_settings,
    get_today_journal,
    create_journal_day,
    complete_day,
    save_settings,
    get_strategy_summary,
)
from handlers.keyboards import (
    plan_kb,
    confirm_complete_kb,
    strategy_finished_kb,
    main_menu_kb,
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
    calc_progress_percent,
    calc_planned_balance,
    format_money,
    format_date,
)

logger = logging.getLogger(__name__)
router = Router()


async def _get_or_create_today_journal(user_id: int, settings: dict):
    """
    Bugungi journal yozuvini oladi yoki yaratadi.
    Scheduler o'tkazib yuborgan bo'lsa zaxira sifatida ishlaydi.

    Qaytaradi: (journal, day_number) yoki (None, None)
    """
    today = get_current_date(settings["timezone"])
    start_date = parse_start_date(settings["start_date"])
    if not start_date:
        return None, None

    day_number = get_day_number(
        start_date, today,
        settings.get("rest_days", ""),
        settings.get("total_days", 0),
    )
    if not day_number:
        return None, None

    journal = await get_today_journal(user_id, today)

    # Zaxira: journal yo'q bo'lsa yaratamiz
    if not journal:
        start_balance = float(settings.get("starting_balance") or 0)

        # Oldingi kun balansi
        from database.queries import get_journal_range
        from datetime import timedelta
        prev_journals = await get_journal_range(
            user_id,
            start_date,
            today - timedelta(days=1),
        )
        if prev_journals:
            last = prev_journals[-1]
            if last["end_balance"]:
                start_balance = float(last["end_balance"])

        # target_profit — rejalangan balansdan hisoblanadi
        _starting = float(settings.get("starting_balance") or 0)
        _rate     = float(settings.get("daily_profit_rate") or 0.1)
        _extra    = float(settings.get("extra_target") or 0)
        _wamt     = float(settings.get("withdrawal_amount") or 0)
        _wevery   = int(settings.get("withdrawal_every") or 0)

        planned_start = calc_planned_balance(
            _starting, _rate, day_number - 1, _extra, _wamt, _wevery
        )
        target_profit = calc_target_profit(planned_start, _rate)

        withdrawal_every   = _wevery
        _is_withdrawal_day = is_withdrawal_day(day_number, _wevery) if _wevery > 0 else False

        journal = await create_journal_day(
            user_id=user_id,
            day_number=day_number,
            today=today,
            start_balance=start_balance,
            target_profit=target_profit,
            extra_target=float(settings.get("extra_target") or 0),
            withdrawal_amount=float(settings.get("withdrawal_amount") or 0) if _is_withdrawal_day else 0,
            is_withdrawal_day=_is_withdrawal_day,
        )

    return journal, day_number


def _format_plan_message(journal: dict, settings: dict, day_number: int) -> str:
    """
    Bugungi reja xabarini formatlaydi.
    """
    total_target = calc_total_target(
        float(journal["target_profit"]),
        float(journal["extra_target"]),
        float(journal["carry_over_amount"]),
    )
    current_pnl = float(journal["actual_pnl"] or 0)
    remaining = calc_remaining(total_target, current_pnl)
    progress = calc_progress_percent(current_pnl, total_target)

    # Rejalangan balans
    _withdrawal_every = int(settings.get("withdrawal_every") or 0)
    planned = calc_planned_balance(
        float(settings.get("starting_balance") or 0),
        float(settings.get("daily_profit_rate") or 0.1),
        day_number,
        float(settings.get("extra_target") or 0),
        float(settings.get("withdrawal_amount") or 0) if _withdrawal_every > 0 else 0,
        _withdrawal_every,
    )

    pnl_icon = "🟢" if current_pnl >= 0 else "🔴"

    # Progress — 100% dan oshishi mumkin
    progress = round((current_pnl / total_target * 100), 1) if total_target > 0 else 0

    # Qoldi — maqsad bajarilgan bo'lsa "Maqsad bajarildi!" ko'rsatiladi
    if remaining <= 0:
        remaining_line = "✅ Maqsad bajarildi!"
    else:
        remaining_line = f"⏳ Qoldi: {format_money(remaining)}"

    carry_line = ""
    if float(journal["carry_over_amount"]) > 0:
        carry_line = f"\n  • Rollover: +{format_money(float(journal['carry_over_amount']))}"

    withdrawal_line = ""
    if journal["is_withdrawal_day"]:
        status = "✅ Tasdiqlangan" if journal["withdrawal_confirmed"] else "⏳ Tasdiqlanmagan"
        withdrawal_line = f"\n💸 Yechish: {format_money(float(journal['withdrawal_amount']))} — {status}"

    return (
        f"📊 <b>Bugungi reja</b>\n"
        f"{'─' * 20}\n"
        f"📅 <b>{day_number}-kun</b> / {settings.get('total_days', '?')}\n"
        f"💰 Haqiqiy balans: <b>{format_money(float(journal['start_balance']))}</b>\n"
        f"📈 Rejalangan: {format_money(planned)}\n\n"
        f"🎯 <b>Bugungi maqsad:</b>\n"
        f"  • Foiz foydasi: {format_money(float(journal['target_profit']))}\n"
        f"  • Qo'shimcha: {format_money(float(journal['extra_target']))}"
        f"{carry_line}\n"
        f"  • Jami: <b>{format_money(total_target)}</b>\n\n"
        f"{pnl_icon} Hozirgi PnL: <b>{format_money(current_pnl)}</b>\n"
        f"📊 Progress: {progress}%\n"
        f"{remaining_line}"
        f"{withdrawal_line}"
    )


@router.message(F.text == "📊 Bugungi reja")
async def show_plan(message: Message, user_id: int, **kwargs) -> None:
    """
    Bugungi reja ko'rsatish.
    """
    try:
        settings = await get_settings(user_id)

        if not settings or not settings["is_active"]:
            await message.answer(
                "⚙️ Avval sozlamalarni to'ldiring.",
                reply_markup=main_menu_kb(),
            )
            return

        # Strategiya tugaganmi?
        start_date = parse_start_date(settings["start_date"] or "")
        if start_date:
            today = get_current_date(settings["timezone"])
            if is_strategy_finished(
                start_date, today,
                settings.get("rest_days", ""),
                settings.get("total_days", 0),
            ):
                summary = await get_strategy_summary(user_id)
                await message.answer(
                    _format_strategy_finished(summary),
                    reply_markup=strategy_finished_kb(),
                    parse_mode="HTML",
                )
                return

        # Dam olish kunimi?
        today = get_current_date(settings["timezone"])
        if is_rest_day(today, settings.get("rest_days", "")):
            await message.answer(
                "😴 Bugun dam olish kuni.\nYaxshi dam oling!",
                reply_markup=main_menu_kb(),
            )
            return

        journal, day_number = await _get_or_create_today_journal(user_id, settings)

        if not journal or not day_number:
            await message.answer(
                "⚠️ Strategiya hali boshlanmagan yoki sozlamalar to'liq emas.",
                reply_markup=main_menu_kb(),
            )
            return

        # Kun allaqachon yakunlanganmi?
        if journal["is_completed"]:
            net_pnl = float(journal["net_pnl"] or 0)
            end_balance = float(journal["end_balance"] or 0)
            total_target = calc_total_target(
                float(journal["target_profit"]),
                float(journal["extra_target"]),
                float(journal["carry_over_amount"]),
            )
            if not journal["is_rolled_over"]:
                result_line = "✅ Maqsad bajarildi!"
            else:
                missing = calc_remaining(total_target, net_pnl)
                result_line = f"❌ Maqsad bajarilmadi. {format_money(missing)} keyingi kunga o'tadi."

            await message.answer(
                f"📊 <b>{day_number}-kun yakunlangan</b>\n"
                f"{'─' * 20}\n"
                f"🎯 Maqsad: <b>{format_money(total_target)}</b>\n"
                f"💰 Net PnL: <b>{format_money(net_pnl)}</b>\n"
                f"🏦 Yakuniy balans: <b>{format_money(end_balance)}</b>\n\n"
                f"{result_line}",
                reply_markup=main_menu_kb(),
                parse_mode="HTML",
            )
            return

        text = _format_plan_message(journal, settings, day_number)
        await message.answer(
            text,
            reply_markup=plan_kb(
                is_withdrawal_day=journal["is_withdrawal_day"],
                withdrawal_confirmed=journal["withdrawal_confirmed"],
                webapp_url=WEBAPP_URL,
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"show_plan xato [user_id={user_id}]: {e}")
        await message.answer("⚠️ Xato yuz berdi. Qaytadan urinib ko'ring.")


@router.callback_query(F.data == "plan_refresh")
async def refresh_plan(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """
    Rejani yangilash callback.
    """
    try:
        settings = await get_settings(user_id)
        if not settings or not settings["is_active"]:
            await callback.answer("Sozlamalar to'liq emas.", show_alert=True)
            return

        journal, day_number = await _get_or_create_today_journal(user_id, settings)
        if not journal or not day_number:
            await callback.answer("Ma'lumot topilmadi.", show_alert=True)
            return

        text = _format_plan_message(journal, settings, day_number)
        await callback.message.edit_text(
            text,
            reply_markup=plan_kb(
                is_withdrawal_day=journal["is_withdrawal_day"],
                withdrawal_confirmed=journal["withdrawal_confirmed"],
                webapp_url=WEBAPP_URL,
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"refresh_plan xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


@router.callback_query(F.data == "confirm_withdrawal")
async def confirm_withdrawal(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """
    Yechishni tasdiqlash.
    """
    try:
        settings = await get_settings(user_id)
        today = get_current_date(settings["timezone"])
        journal = await get_today_journal(user_id, today)

        if not journal:
            await callback.answer("Bugungi jurnal topilmadi.", show_alert=True)
            return

        from database.connection import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE daily_journal
                SET withdrawal_confirmed = TRUE
                WHERE user_id = $1 AND date = $2;
            """, user_id, today)

        await callback.answer("✅ Yechish tasdiqlandi!", show_alert=False)

        # Rejani yangilash
        journal, day_number = await _get_or_create_today_journal(user_id, settings)
        text = _format_plan_message(journal, settings, day_number)
        await callback.message.edit_text(
            text,
            reply_markup=plan_kb(
                is_withdrawal_day=True,
                withdrawal_confirmed=True,
                webapp_url=WEBAPP_URL,
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"confirm_withdrawal xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)


@router.callback_query(F.data == "complete_day")
async def ask_complete_day(callback: CallbackQuery, **kwargs) -> None:
    """
    Kunni yakunlash — tasdiqlash so'rovi.
    """
    await callback.message.edit_text(
        "✅ <b>Kunni yakunlashni tasdiqlaysizmi?</b>\n\n"
        "Yakunlangandan so'ng savdo qo'shib bo'lmaydi.",
        reply_markup=confirm_complete_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_complete")
async def do_complete_day(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """
    Kunni yakunlash — tasdiqlangandan keyin.
    """
    try:
        settings = await get_settings(user_id)
        today = get_current_date(settings["timezone"])
        journal = await get_today_journal(user_id, today)

        if not journal:
            await callback.answer("Bugungi jurnal topilmadi.", show_alert=True)
            return

        updated = await complete_day(user_id, journal["day_number"])
        if not updated:
            await callback.answer("⚠️ Yakunlashda xato.", show_alert=True)
            return

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
            rollover_text = f"\n⚠️ Maqsad bajarilmadi. {format_money(missing)} keyingi kunga o'tadi."

        await callback.message.edit_text(
            f"{icon} <b>Kun yakunlandi!</b>\n\n"
            f"💰 Net PnL: <b>{format_money(net_pnl)}</b>\n"
            f"🏦 Yangi balans: <b>{format_money(end_balance)}</b>"
            f"{rollover_text}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"do_complete_day xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_complete(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """
    Yakunlashni bekor qilish — rejaga qaytish.
    """
    try:
        settings = await get_settings(user_id)
        journal, day_number = await _get_or_create_today_journal(user_id, settings)
        if not journal:
            await callback.answer()
            return
        text = _format_plan_message(journal, settings, day_number)
        await callback.message.edit_text(
            text,
            reply_markup=plan_kb(
                is_withdrawal_day=journal["is_withdrawal_day"],
                withdrawal_confirmed=journal["withdrawal_confirmed"],
                webapp_url=WEBAPP_URL,
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"cancel_complete xato [user_id={user_id}]: {e}")
    finally:
        await callback.answer()


def _format_strategy_finished(summary: dict) -> str:
    """
    Strategiya tugash xabarini formatlaydi.
    """
    if not summary:
        return "🏁 <b>Strategiya yakunlandi!</b>"

    profit = summary["final_balance"] - summary["starting_balance"]
    return (
        f"🏁 <b>Strategiya yakunlandi!</b>\n"
        f"{'─' * 20}\n"
        f"📅 Jami kunlar: {summary['total_days']}\n"
        f"✅ Maqsad bajarildi: {summary['win_days']} kun\n"
        f"❌ Bajarilmadi: {summary['loss_days']} kun\n"
        f"🎯 Win rate: {summary['win_rate']}%\n\n"
        f"💰 Boshlang'ich balans: {format_money(summary['starting_balance'])}\n"
        f"🏦 Yakuniy balans: {format_money(summary['final_balance'])}\n"
        f"📈 Jami foyda: {format_money(profit)}\n"
        f"💸 Jami yechildi: {format_money(summary['total_withdrawal'])}"
    )
