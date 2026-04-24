from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database.queries import (
    get_settings, get_today_journal, create_today_journal,
    update_journal_pnl, complete_day, confirm_withdrawal,
    get_trades_by_day
)
from utils.calculator import (
    get_current_day,
    is_withdrawal_day, calculate_balance_progression
)
from handlers.keyboards import plan_inline, confirm_keyboard
from utils.logger import logger

router = Router()


async def build_plan_text(user_id: int) -> tuple[str, dict]:
    settings = await get_settings(user_id)
    if not settings:
        return "⚠️ Sozlamalar topilmadi.", {}

    day = get_current_day(settings["start_date"], settings["total_days"])
    total_days = settings["total_days"]

    if day > total_days:
        return (
            "🎉 Strategiya davri tugadi!\n\n"
            "Yangi strategiya boshlash uchun <b>⚙️ Sozlamalar</b> ga kiring.",
            {}
        )

    progression = calculate_balance_progression(settings)
    day_data = progression[day - 1] if day <= len(progression) else progression[-1]

    start_balance = day_data["start_balance"]
    profit_target = day_data["profit_target"]
    extra_target = day_data["extra_target"]
    total_target = day_data["total_target"]
    is_wday = day_data["is_withdrawal_day"]
    withdrawal = day_data["withdrawal"]

    journal = await get_today_journal(user_id)
    if not journal:
        journal = await create_today_journal(
            user_id=user_id,
            day_number=day,
            start_balance=start_balance,
            target_profit=profit_target,
            extra_target=extra_target,
            is_withdrawal_day=is_wday,
            withdrawal_amount=withdrawal
        )

    await update_journal_pnl(user_id)
    journal = await get_today_journal(user_id)
    actual_pnl = float(journal.get("actual_pnl") or 0) if journal else 0.0
    total_target = float(total_target)
    start_balance = float(start_balance)
    profit_target = float(profit_target)
    extra_target = float(extra_target)
    withdrawal = float(withdrawal)
    remaining = round(total_target - actual_pnl, 2)

    trades = await get_trades_by_day(user_id, day)
    trades_text = ""
    if trades:
        trades_text = "\n\n📋 <b>Bugungi savdolar:</b>\n"
        for t in trades:
            pnl_val = float(t["pnl"] or 0)
            sign = "+" if pnl_val >= 0 else ""
            emoji = "🟢" if pnl_val >= 0 else "🔴"
            trades_text += f"{emoji} {t['symbol']} {t['direction']} → {sign}{pnl_val}$\n"

    pnl_emoji = "🟢" if actual_pnl >= 0 else "🔴"
    rem_emoji = "✅" if remaining <= 0 else "⏳"

    text = (
        f"📊 <b>Bugungi reja</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 {day}-kun / {total_days}\n"
        f"💰 Joriy balans: <b>{start_balance}$</b>\n\n"
        f"🎯 <b>Bugungi maqsad:</b>\n"
        f"   • Foiz foydasi: +{profit_target}$\n"
        f"   • Qo'shimcha: +{extra_target}$\n"
        f"   • Jami: <b>+{total_target}$</b>\n\n"
        f"{pnl_emoji} Hozirgi PnL: <b>{'+' if actual_pnl >= 0 else ''}{actual_pnl}$</b>\n"
        f"{rem_emoji} Qoldi: <b>{max(0, remaining)}$</b>"
        f"{trades_text}"
    )

    if is_wday:
        wc = journal.get("withdrawal_confirmed", False) if journal else False
        if wc:
            text += f"\n\n💸 Yechish tasdiqlandi: <b>{withdrawal}$</b> ✅"
        else:
            text += f"\n\n⚠️ <b>Bugun yechish kuni!</b> Yechish summasi: <b>{withdrawal}$</b>"

    return text, {"is_withdrawal_day": is_wday,
                  "withdrawal_confirmed": journal.get("withdrawal_confirmed", False) if journal else False,
                  "remaining": remaining,
                  "actual_pnl": actual_pnl,
                  "total_target": total_target}


@router.message(F.text == "📊 Bugungi reja")
async def plan_handler(message: Message, db_user_id: int, settings_complete: bool):
    if not settings_complete:
        await message.answer("⚠️ Avval <b>⚙️ Sozlamalar</b>ni to'ldiring.", parse_mode="HTML")
        return

    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)

    await message.answer(
        text,
        reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "plan_refresh")
async def plan_refresh(call: CallbackQuery, db_user_id: int, settings_complete: bool):
    if not settings_complete:
        await call.answer("Sozlamalar to'ldirilmagan!", show_alert=True)
        return
    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)
    try:
        await call.message.edit_text(
            text,
            reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await call.answer("🔄 Yangilandi")


@router.callback_query(F.data == "confirm_withdrawal")
async def ask_confirm_withdrawal(call: CallbackQuery):
    await call.message.edit_text(
        "💸 Rostdan ham yechishni tasdiqlaysizmi?\n\nYechish summasi ko'rsatilgan miqdorga o'zgaradi.",
        reply_markup=confirm_keyboard("withdrawal"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "confirm_withdrawal_yes")
async def do_confirm_withdrawal(call: CallbackQuery, db_user_id: int):
    await confirm_withdrawal(db_user_id)
    logger.info(f"Yechish tasdiqlandi: user_id={db_user_id}")
    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)
    await call.message.edit_text(
        text,
        reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc),
        parse_mode="HTML"
    )
    await call.answer("✅ Yechish tasdiqlandi!")


@router.callback_query(F.data == "complete_day")
async def ask_complete_day(call: CallbackQuery):
    await call.message.edit_text(
        "✅ Kunni yakunlashni tasdiqlaysizmi?\n\nYakunlangandan so'ng bugungi balans saqlanadi.",
        reply_markup=confirm_keyboard("complete"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "confirm_complete")
async def do_complete_day(call: CallbackQuery, db_user_id: int):
    from database.queries import get_today_journal
    journal = await get_today_journal(db_user_id)
    if not journal:
        await call.answer("Bugungi jurnal topilmadi!", show_alert=True)
        return

    if journal.get("is_completed"):
        await call.answer("Kun allaqachon yakunlangan!", show_alert=True)
        return

    info = await build_plan_text(db_user_id)
    remaining = info[1].get("remaining", 0)
    actual_pnl = info[1].get("actual_pnl", 0)
    total_target = info[1].get("total_target", 0)

    completed = await complete_day(db_user_id)
    logger.info(f"Kun yakunlandi: user_id={db_user_id}, PnL={actual_pnl}")

    end_balance = completed.get("end_balance", 0)

    if actual_pnl >= total_target:
        result_msg = f"🎉 <b>Tabriklaymiz! Maqsad bajarildi!</b>\n\n"
    elif actual_pnl > 0:
        result_msg = f"📊 Kun yakunlandi.\n\n"
    elif actual_pnl < 0:
        result_msg = f"⚠️ Bugun zarar bilan yakunlandi. Ertaga yanada yaxshi!\n\n"
    else:
        result_msg = f"📊 Kun yakunlandi.\n\n"

    result_msg += (
        f"💰 Yakuniy balans: <b>{end_balance}$</b>\n"
        f"📈 Bugungi PnL: <b>{'+' if actual_pnl >= 0 else ''}{actual_pnl}$</b>"
    )

    await call.message.edit_text(result_msg, parse_mode="HTML")
    await call.answer("✅ Kun yakunlandi!")


@router.callback_query(F.data == "cancel")
async def cancel_action(call: CallbackQuery, db_user_id: int, settings_complete: bool):
    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)
    try:
        await call.message.edit_text(
            text,
            reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await call.answer()
