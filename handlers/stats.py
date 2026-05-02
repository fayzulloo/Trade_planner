from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, timedelta, datetime
from database.queries import get_settings, get_journal_range, get_all_journals
from utils.calculator import get_strategy_summary, is_weekend
from utils.chart import generate_pnl_chart, generate_balance_chart
from handlers.keyboards import stats_inline, stats_chart_inline
from utils.logger import logger
import os

router = Router()


class StatsForm(StatesGroup):
    from_date = State()
    to_date = State()


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def _format_date(d) -> str:
    if isinstance(d, str):
        return d
    try:
        return d.strftime("%d.%m.%Y")
    except Exception:
        return str(d)


def _journal_summary(journals: list, title: str) -> str:
    if not journals:
        return (
            f"📊 <b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Hali savdo ma'lumotlari yo'q.\n"
            f"Savdo kiriting va grafik ko'rish imkoniyati paydo bo'ladi."
        )
    total_pnl = sum(_safe_float(j.get("actual_pnl")) for j in journals)
    completed = [j for j in journals if j.get("is_completed")]
    winning = [j for j in completed if _safe_float(j.get("actual_pnl")) > 0]
    losing = [j for j in completed if _safe_float(j.get("actual_pnl")) < 0]
    total_target = sum(
        _safe_float(j.get("target_profit")) + _safe_float(j.get("extra_target"))
        for j in journals
    )
    total_target = float(total_target)
    total_pnl = float(total_pnl)
    performance = round(total_pnl / total_target * 100, 1) if total_target else 0
    pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
    sign = "+" if total_pnl >= 0 else ""

    text = (
        f"📊 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 Ish kunlari: <b>{len(journals)}</b>\n"
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
            pnl = _safe_float(j.get("actual_pnl"))
            e = "🟢" if pnl >= 0 else "🔴"
            s = "+" if pnl >= 0 else ""
            d = _format_date(j.get("date", ""))
            text += f"{e} {d}: {s}{pnl:.2f}$\n"
    return text


async def _send_stats(call: CallbackQuery, journals: list, title: str, chart_key: str):
    text = _journal_summary(journals, title)
    try:
        await call.message.edit_text(
            text,
            reply_markup=stats_chart_inline(chart_key),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Stats edit_text xato: {e}")
        await call.message.answer(text, reply_markup=stats_chart_inline(chart_key), parse_mode="HTML")
    await call.answer()


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
    await _send_stats(call, journals, "Kunlik statistika", "daily")


@router.callback_query(F.data == "stats_weekly")
async def stats_weekly(call: CallbackQuery, db_user_id: int):
    to_d = date.today().isoformat()
    from_d = (date.today() - timedelta(days=6)).isoformat()
    journals = await get_journal_range(db_user_id, from_d, to_d)
    await _send_stats(call, journals, "Haftalik statistika", "weekly")


@router.callback_query(F.data == "stats_monthly")
async def stats_monthly(call: CallbackQuery, db_user_id: int):
    today = date.today()
    from_d = today.replace(day=1).isoformat()
    to_d = today.isoformat()
    journals = await get_journal_range(db_user_id, from_d, to_d)
    await _send_stats(call, journals, "Oylik statistika", "monthly")


@router.callback_query(F.data == "stats_strategy")
async def stats_strategy(call: CallbackQuery, db_user_id: int):
    settings = await get_settings(db_user_id)
    journals = await get_all_journals(db_user_id)
    summary = get_strategy_summary(settings, journals)

    pnl_emoji = "🟢" if summary["total_actual_profit"] >= 0 else "🔴"
    sign = "+" if summary["total_actual_profit"] >= 0 else ""
    final_bal = summary.get("real_balance") or summary.get("final_balance") or 0
    final_bal_str = f"{final_bal:.2f}" if final_bal is not None else "—"

    text = (
        f"🎯 <b>Strategiya davri natijasi</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 Jami ish kun: <b>{summary['total_days']}</b>\n"
        f"✅ Bajarilgan: <b>{summary['completed_days']}</b>\n"
        f"💰 Boshlang'ich: <b>{summary['starting_balance']:.2f}$</b>\n"
        f"💼 Yakuniy balans: <b>{final_bal_str}$</b>\n"
        f"🎯 Rejalangan foyda: <b>{summary['total_expected_profit']:.2f}$</b>\n"
        f"{pnl_emoji} Haqiqiy foyda: <b>{sign}{summary['total_actual_profit']:.2f}$</b>\n"
        f"💸 Jami yechilgan: <b>{summary['total_withdrawn']:.2f}$</b>\n"
        f"📈 Samaradorlik: <b>{summary['performance_pct']}%</b>\n"
    )
    try:
        await call.message.edit_text(
            text, reply_markup=stats_chart_inline("strategy"), parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"stats_strategy xato: {e}")
        await call.message.answer(text, reply_markup=stats_chart_inline("strategy"), parse_mode="HTML")
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
        await message.answer("⚠️ Format noto'g'ri:\n<i>01.04.2025</i>", parse_mode="HTML")


@router.message(StatsForm.to_date)
async def stats_range_to(message: Message, state: FSMContext, db_user_id: int):
    try:
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
        data = await state.get_data()
        from_d = datetime.strptime(data["from_date"], "%d.%m.%Y").date().isoformat()
        to_d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date().isoformat()
        await state.clear()
        journals = await get_journal_range(db_user_id, from_d, to_d)
        text = _journal_summary(journals, f"📅 {data['from_date']} — {message.text.strip()}")
        await message.answer(text, reply_markup=stats_chart_inline("range"), parse_mode="HTML")
    except ValueError:
        await message.answer("⚠️ Format noto'g'ri:\n<i>30.04.2025</i>", parse_mode="HTML")


# ===== CHARTS =====
@router.callback_query(F.data.startswith("chart_"))
async def show_chart(call: CallbackQuery, db_user_id: int):
    period = call.data[6:]
    await call.answer("📊 Grafik tayyorlanmoqda...")

    settings = await get_settings(db_user_id)
    today = date.today()

    if period == "daily":
        journals = await get_journal_range(db_user_id, today.isoformat(), today.isoformat())
        title = "Kunlik"
    elif period == "weekly":
        journals = await get_journal_range(
            db_user_id, (today - timedelta(days=6)).isoformat(), today.isoformat()
        )
        title = "Haftalik"
    elif period == "monthly":
        journals = await get_journal_range(
            db_user_id, today.replace(day=1).isoformat(), today.isoformat()
        )
        title = "Oylik"
    else:
        journals = await get_all_journals(db_user_id)
        title = "Strategiya davri"

    # Bo'sh bo'lsa ham grafik yuboramiz (bo'sh grafik)
    if not journals:
        from datetime import date as dt
        journals = [{
            "date": today.isoformat(),
            "actual_pnl": 0,
            "target_profit": 0,
            "extra_target": 0,
            "is_completed": False
        }]

    pnl_path = generate_pnl_chart(journals, title=title)
    bal_path = generate_balance_chart(journals, settings, title=f"{title} — Balans")

    sent = False
    try:
        if pnl_path and os.path.exists(pnl_path):
            await call.message.answer_photo(
                FSInputFile(pnl_path), caption=f"📊 {title} — PnL grafigi"
            )
            os.remove(pnl_path)
            sent = True
        if bal_path and os.path.exists(bal_path):
            await call.message.answer_photo(
                FSInputFile(bal_path), caption=f"📈 {title} — Balans o'sishi"
            )
            os.remove(bal_path)
            sent = True
    except Exception as e:
        logger.error(f"Grafik yuborishda xato: {e}")
        await call.message.answer("⚠️ Grafik yaratishda xato yuz berdi.")

    # Inline tugmalarni o'chiramiz
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data == "stats_back")
async def stats_back(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(
            "📈 <b>Statistika</b>\n\nQaysi davrni ko'rmoqchisiz?",
            reply_markup=stats_inline(), parse_mode="HTML"
        )
    except Exception:
        await call.message.answer(
            "📈 <b>Statistika</b>\n\nQaysi davrni ko'rmoqchisiz?",
            reply_markup=stats_inline(), parse_mode="HTML"
        )
    await call.answer()
