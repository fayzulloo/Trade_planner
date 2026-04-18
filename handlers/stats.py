from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, timedelta, datetime
from database.queries import (
    get_settings, get_journal_range, get_all_journals, get_today_journal
)
from utils.calculator import get_strategy_summary
from utils.chart import generate_pnl_chart, generate_balance_chart
from handlers.keyboards import stats_inline, stats_chart_inline
from utils.logger import logger
import os

router = Router()


class StatsForm(StatesGroup):
    from_date = State()
    to_date = State()


def _journal_summary(journals: list, title: str) -> str:
    if not journals:
        return f"📊 <b>{title}</b>\n\nMa'lumot topilmadi."
    total_pnl = sum(j.get("actual_pnl", 0) for j in journals)
    completed = [j for j in journals if j.get("is_completed")]
    winning = [j for j in completed if j.get("actual_pnl", 0) > 0]
    losing = [j for j in completed if j.get("actual_pnl", 0) < 0]
    total_target = sum(
        j.get("target_profit", 0) + j.get("extra_target", 0) for j in journals
    )
    performance = round(total_pnl / total_target * 100, 1) if total_target else 0
    pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
    sign = "+" if total_pnl >= 0 else ""

    text = (
        f"📊 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 Kunlar: <b>{len(journals)}</b>\n"
        f"✅ Yakunlangan: <b>{len(completed)}</b>\n"
        f"🎯 Maqsad: <b>{total_target:.2f}$</b>\n"
        f"{pnl_emoji} Haqiqiy PnL: <b>{sign}{total_pnl:.2f}$</b>\n"
        f"📈 Samaradorlik: <b>{performance}%</b>\n"
        f"🟢 Foydali kunlar: <b>{len(winning)}</b>\n"
        f"🔴 Zararli kunlar: <b>{len(losing)}</b>\n"
    )
    if journals:
        text += "\n<b>Kunlik ko'rinish:</b>\n"
        for j in journals[-7:]:
            pnl = j.get("actual_pnl", 0)
            e = "🟢" if pnl >= 0 else "🔴"
            s = "+" if pnl >= 0 else ""
            text += f"{e} {j['date']}: {s}{pnl:.2f}$\n"
    return text


@router.message(F.text == "📈 Statistika")
async def stats_handler(message: Message, db_user_id: int, settings_complete: bool):
    if not settings_complete:
        await message.answer("⚠️ Avval <b>⚙️ Sozlamalar</b>ni to'ldiring.", parse_mode="HTML")
        return
    await message.answer(
        "📈 <b>Statistika</b>\n\nQaysi davrni ko'rmoqchisiz?",
        reply_markup=stats_inline(), parse_mode="HTML"
    )


@router.callback_query(F.data == "stats_daily")
async def stats_daily(call: CallbackQuery, db_user_id: int):
    today = date.today().isoformat()
    journals = await get_journal_range(db_user_id, today, today)
    text = _journal_summary(journals, "Kunlik statistika")
    await call.message.edit_text(
        text,
        reply_markup=stats_chart_inline("daily"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "stats_weekly")
async def stats_weekly(call: CallbackQuery, db_user_id: int):
    to_date = date.today().isoformat()
    from_date = (date.today() - timedelta(days=6)).isoformat()
    journals = await get_journal_range(db_user_id, from_date, to_date)
    text = _journal_summary(journals, "Haftalik statistika")
    await call.message.edit_text(
        text,
        reply_markup=stats_chart_inline("weekly"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "stats_monthly")
async def stats_monthly(call: CallbackQuery, db_user_id: int):
    today = date.today()
    from_date = today.replace(day=1).isoformat()
    to_date = today.isoformat()
    journals = await get_journal_range(db_user_id, from_date, to_date)
    text = _journal_summary(journals, "Oylik statistika")
    await call.message.edit_text(
        text,
        reply_markup=stats_chart_inline("monthly"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "stats_strategy")
async def stats_strategy(call: CallbackQuery, db_user_id: int):
    settings = await get_settings(db_user_id)
    journals = await get_all_journals(db_user_id)
    summary = get_strategy_summary(settings, journals)

    pnl_emoji = "🟢" if summary["total_actual_profit"] >= 0 else "🔴"
    sign = "+" if summary["total_actual_profit"] >= 0 else ""

    text = (
        f"🎯 <b>Strategiya davri natijasi</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 Jami kun: <b>{summary['total_days']}</b>\n"
        f"✅ Bajarilgan: <b>{summary['completed_days']}</b>\n"
        f"💰 Boshlang'ich: <b>{summary['starting_balance']}$</b>\n"
        f"💼 Yakuniy balans: <b>{summary['final_balance']}$</b>\n"
        f"🎯 Rejalangan foyda: <b>{summary['total_expected_profit']}$</b>\n"
        f"{pnl_emoji} Haqiqiy foyda: <b>{sign}{summary['total_actual_profit']}$</b>\n"
        f"💸 Jami yechilgan: <b>{summary['total_withdrawn']}$</b>\n"
        f"📈 Samaradorlik: <b>{summary['performance_pct']}%</b>\n"
    )
    await call.message.edit_text(
        text,
        reply_markup=stats_chart_inline("strategy"),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "stats_range")
async def stats_range_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(StatsForm.from_date)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="stats_back")]
    ])
    await call.message.edit_text(
        "🔢 <b>Boshlang'ich sanani kiriting:</b>\n<i>Format: 01.04.2025</i>",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()


@router.message(StatsForm.from_date)
async def stats_range_from(message: Message, state: FSMContext):
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await state.update_data(from_date=message.text.strip())
        await state.set_state(StatsForm.to_date)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="stats_back")]
        ])
        await message.answer(
            "🔢 <b>Yakuniy sanani kiriting:</b>\n<i>Format: 30.04.2025</i>",
            reply_markup=kb, parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ Format noto'g'ri. Qayta kiriting:\n<i>01.04.2025</i>", parse_mode="HTML")


@router.message(StatsForm.to_date)
async def stats_range_to(message: Message, state: FSMContext, db_user_id: int):
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
        data = await state.get_data()
        from_date = datetime.strptime(data["from_date"], "%d.%m.%Y").date().isoformat()
        to_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date().isoformat()
        await state.clear()
        journals = await get_journal_range(db_user_id, from_date, to_date)
        text = _journal_summary(journals, f"📅 {data['from_date']} — {message.text.strip()}")
        await message.answer(
            text,
            reply_markup=stats_chart_inline("range"),
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ Format noto'g'ri. Qayta kiriting:\n<i>30.04.2025</i>", parse_mode="HTML")


# ===== CHARTS =====
@router.callback_query(F.data.startswith("chart_"))
async def show_chart(call: CallbackQuery, db_user_id: int):
    period = call.data[6:]
    await call.answer("📊 Grafik tayyorlanmoqda...")

    settings = await get_settings(db_user_id)
    today = date.today()

    if period == "daily":
        journals = await get_journal_range(db_user_id, today.isoformat(), today.isoformat())
        title = "Kunlik PnL"
    elif period == "weekly":
        journals = await get_journal_range(
            db_user_id,
            (today - timedelta(days=6)).isoformat(),
            today.isoformat()
        )
        title = "Haftalik PnL"
    elif period == "monthly":
        journals = await get_journal_range(
            db_user_id, today.replace(day=1).isoformat(), today.isoformat()
        )
        title = "Oylik PnL"
    else:
        journals = await get_all_journals(db_user_id)
        title = "Strategiya davri"

    if not journals:
        await call.message.answer("📊 Grafik uchun ma'lumot yetarli emas.")
        return

    pnl_path = generate_pnl_chart(journals, title=title)
    bal_path = generate_balance_chart(journals, settings, title=f"{title} — Balans")

    try:
        if pnl_path and os.path.exists(pnl_path):
            await call.message.answer_photo(
                FSInputFile(pnl_path),
                caption=f"📊 {title} — PnL grafigi"
            )
            os.remove(pnl_path)

        if bal_path and os.path.exists(bal_path):
            await call.message.answer_photo(
                FSInputFile(bal_path),
                caption=f"📈 {title} — Balans o'sishi"
            )
            os.remove(bal_path)
    except Exception as e:
        logger.error(f"Grafik yuborishda xato: {e}")
        await call.message.answer("⚠️ Grafik yaratishda xato yuz berdi.")

    await call.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data == "stats_back")
async def stats_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "📈 <b>Statistika</b>\n\nQaysi davrni ko'rmoqchisiz?",
        reply_markup=stats_inline(), parse_mode="HTML"
    )
    await call.answer()
