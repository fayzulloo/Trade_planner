from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database.queries import (
    get_settings, get_today_journal, create_today_journal,
    update_journal_pnl, complete_day, confirm_withdrawal,
    get_trades_by_day, get_real_balance
)
from utils.calculator import (
    get_current_day, is_withdrawal_day,
    calculate_balance_progression, is_today_rest_day,
    parse_rest_days
)
from handlers.keyboards import plan_inline, confirm_keyboard
from utils.logger import logger
from datetime import datetime, date as date_type

router = Router()


async def build_plan_text(user_id: int) -> tuple[str, dict]:
    settings = await get_settings(user_id)
    if not settings:
        return "⚠️ Sozlamalar topilmadi.", {}

    rest_days = parse_rest_days(settings.get("rest_days") or "6,7")

    # Dam olish kuni tekshiruvi
    if is_today_rest_day(rest_days):
        day_name = date_type.today().strftime("%A")
        return (
            f"🏖 <b>Bugun dam olish kuni!</b>\n\n"
            f"Bugungi rejalar yo'q. Yaxshi dam oling! 😊",
            {}
        )

    # Strategiya boshlanmagan tekshiruvi
    if settings.get("start_date"):
        start = datetime.strptime(settings["start_date"], "%d.%m.%Y").date()
        if start > date_type.today():
            days_left = (start - date_type.today()).days
            return (
                f"⏳ <b>Strategiya hali boshlanmagan</b>\n\n"
                f"📆 Boshlanish: <b>{settings['start_date']}</b>\n"
                f"🕐 Qoldi: <b>{days_left} kun</b>",
                {}
            )

    day = get_current_day(settings["start_date"], settings["total_days"], rest_days)
    total_days = int(settings["total_days"])

    if day > total_days:
        return (
            "🎉 Strategiya davri tugadi!\n\n"
            "Yangi strategiya boshlash uchun <b>⚙️ Sozlamalar</b> ga kiring.",
            {}
        )

    # Journals bilan birga hisoblash — rollover ma'lumotlari uchun
    from database.queries import get_all_journals
    journals = await get_all_journals(user_id)
    progression = calculate_balance_progression(settings, journals)
    if day > len(progression):
        day = len(progression)
    day_data = progression[day - 1]

    start_balance = day_data["start_balance"]
    profit_target = float(day_data["profit_target"])
    extra_target_val = float(day_data["extra_target"])
    carry_over = float(day_data["carry_over"])
    total_target = float(day_data["total_target"])
    is_wday = day_data["is_withdrawal_day"]
    withdrawal = float(day_data["withdrawal"])
    is_rolled = day_data["is_rolled_over"]

    journal = await get_today_journal(user_id)
    if not journal:
        journal = await create_today_journal(
            user_id=user_id,
            day_number=day,
            start_balance=start_balance,
            target_profit=profit_target,
            extra_target=extra_target_val,
            is_withdrawal_day=is_wday,
            withdrawal_amount=withdrawal,
            carry_over_amount=carry_over,
        )

    await update_journal_pnl(user_id)
    journal = await get_today_journal(user_id)
    actual_pnl = float(journal.get("actual_pnl") or 0) if journal else 0.0
    remaining = round(total_target - actual_pnl, 2)

    # Haqiqiy joriy balans
    real_balance = await get_real_balance(user_id, float(settings["starting_balance"]))

    trades = await get_trades_by_day(user_id, day)
    trades_text = ""
    if trades:
        trades_text = "\n\n📋 <b>Bugungi savdolar:</b>\n"
        for t in trades:
            pnl_val = float(t["pnl"] or 0)
            swap_val = float(t.get("swap") or 0)
            comm_val = float(t.get("commission") or 0)
            net = round(pnl_val + swap_val + comm_val, 2)
            sign = "+" if net >= 0 else ""
            emoji = "🟢" if net >= 0 else "🔴"
            order = f" #{t['order_id']}" if t.get("order_id") else ""
            trades_text += f"{emoji} {t['symbol']} {t['direction']}{order} → {sign}{net}$\n"

    pnl_emoji = "🟢" if actual_pnl >= 0 else "🔴"
    rem_emoji = "✅" if remaining <= 0 else "⏳"

    rollover_text = ""
    if is_rolled and carry_over > 0:
        rollover_text = f"\n🔄 <b>Rollover:</b> +{carry_over}$ (kechagi qoldiq)\n"

    text = (
        f"📊 <b>Bugungi reja</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 {day}-kun / {total_days}\n"
        f"💰 Haqiqiy balans: <b>{real_balance}$</b>\n"
        f"📈 Rejalangan: <b>{start_balance}$</b>\n\n"
        f"🎯 <b>Bugungi maqsad:</b>\n"
        f"   • Foiz foydasi: +{profit_target}$\n"
        f"   • Qo'shimcha: +{extra_target_val}$\n"
    )
    if carry_over > 0:
        text += f"   • Rollover: +{carry_over}$\n"
    text += f"   • Jami: <b>+{total_target}$</b>\n"
    text += rollover_text
    text += (
        f"\n{pnl_emoji} Hozirgi PnL: <b>{'+' if actual_pnl >= 0 else ''}{actual_pnl}$</b>\n"
        f"{rem_emoji} Qoldi: <b>{max(0, remaining)}$</b>"
        f"{trades_text}"
    )

    if is_wday:
        wc = journal.get("withdrawal_confirmed", False) if journal else False
        if wc:
            text += f"\n\n💸 Yechish tasdiqlandi: <b>{withdrawal}$</b> ✅"
        else:
            text += f"\n\n⚠️ <b>Bugun yechish kuni!</b> Summasi: <b>{withdrawal}$</b>"

    return text, {
        "is_withdrawal_day": is_wday,
        "withdrawal_confirmed": journal.get("withdrawal_confirmed", False) if journal else False,
        "remaining": remaining,
        "actual_pnl": actual_pnl,
        "total_target": total_target,
    }


@router.message(F.text == "📊 Bugungi reja")
async def plan_handler(message: Message, db_user_id: int, settings_complete: bool):
    if not settings_complete:
        await message.answer("⚠️ Avval <b>⚙️ Sozlamalar</b>ni to'ldiring.", parse_mode="HTML")
        return
    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)
    await message.answer(text, reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc) if info else None, parse_mode="HTML")


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
            reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc) if info else None,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await call.answer("🔄 Yangilandi")


@router.callback_query(F.data == "confirm_withdrawal")
async def do_confirm_withdrawal(call: CallbackQuery, db_user_id: int, settings_complete: bool):
    if not settings_complete:
        await call.answer("⚠️ Avval sozlamalarni to'ldiring!", show_alert=True)
        return
    await confirm_withdrawal(db_user_id)
    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)
    await call.message.edit_text(text, reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc), parse_mode="HTML")
    await call.answer("✅ Yechish tasdiqlandi!")


@router.callback_query(F.data == "complete_day")
async def ask_complete_day(call: CallbackQuery):
    await call.message.edit_text(
        "✅ Kunni yakunlashni tasdiqlaysizmi?\n\nYakunlangandan so'ng balans saqlanadi.",
        reply_markup=confirm_keyboard("complete"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "confirm_complete")
async def do_complete_day(call: CallbackQuery, db_user_id: int):
    journal = await get_today_journal(db_user_id)
    if not journal:
        await call.answer("Bugungi jurnal topilmadi!", show_alert=True)
        return
    if journal.get("is_completed"):
        await call.answer("Kun allaqachon yakunlangan!", show_alert=True)
        return

    text_info = await build_plan_text(db_user_id)
    actual_pnl = float(text_info[1].get("actual_pnl") or 0)
    total_target = float(text_info[1].get("total_target") or 0)

    completed = await complete_day(db_user_id)
    end_balance = float(completed.get("end_balance") or 0)
    carry_over = float(completed.get("carry_over_out") or 0)      # chiquvchi rollover summasi
    is_rolled = bool(completed.get("is_rolled_out")) if completed else False

    logger.info(f"Kun yakunlandi: user={db_user_id}, pnl={actual_pnl}, rollover={carry_over}")

    if actual_pnl >= total_target:
        result_msg = "🎉 <b>Tabriklaymiz! Maqsad bajarildi!</b>\n\n"
    elif actual_pnl > 0:
        result_msg = "📊 Kun yakunlandi.\n\n"
    elif actual_pnl < 0:
        result_msg = "⚠️ Bugun zarar bilan yakunlandi. Ertaga yanada yaxshi!\n\n"
    else:
        result_msg = "📊 Kun yakunlandi.\n\n"

    result_msg += (
        f"💰 Yakuniy balans: <b>{end_balance}$</b>\n"
        f"📈 Bugungi PnL: <b>{'+' if actual_pnl >= 0 else ''}{actual_pnl}$</b>"
    )

    if is_rolled and carry_over > 0:
        result_msg += f"\n\n🔄 <b>Qolgan {carry_over}$ ertangi kunga surилди</b>"

    await call.message.edit_text(result_msg, parse_mode="HTML")
    await call.answer("✅ Kun yakunlandi!")


@router.callback_query(F.data == "cancel")
async def cancel_action(call: CallbackQuery, db_user_id: int, settings_complete: bool):
    if not settings_complete:
        await call.answer("⚠️ Avval sozlamalarni to'ldiring!", show_alert=True)
        return
    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)
    try:
        await call.message.edit_text(
            text,
            reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc) if info else None,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await call.answer()
