"""
Statistika handlerlari.
Kunlik, haftalik, oylik va strategiya davri statistikasi.
"""

import logging
from datetime import date, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import WEBAPP_URL
from database.queries import get_settings, get_stats, get_journal_range
from handlers.keyboards import stats_menu_kb, stats_result_kb, stats_cancel_kb
from utils.calculator import (
    get_current_date, parse_start_date, get_day_number,
    calc_win_rate, calc_average_pnl, format_money, format_date,
    calc_planned_balance,
)
from utils.chart import create_balance_chart, create_pnl_chart

logger = logging.getLogger(__name__)
router = Router()


class StatsRangeForm(StatesGroup):
    """Muddatni tanlash bosqichlari."""
    date_from = State()
    date_to   = State()


# ─────────────────────────────────────────────
# MENYU
# ─────────────────────────────────────────────

@router.message(F.text == "📈 Statistika")
async def open_stats(message: Message, **kwargs) -> None:
    """Statistika menyusini ochish."""
    await message.answer(
        "📈 <b>Statistika</b>\n\nDavrni tanlang:",
        reply_markup=stats_menu_kb(WEBAPP_URL),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "stats_back")
async def stats_back(callback: CallbackQuery, **kwargs) -> None:
    """Statistika menyusiga qaytish."""
    await callback.message.edit_text(
        "📈 <b>Statistika</b>\n\nDavrni tanlang:",
        reply_markup=stats_menu_kb(WEBAPP_URL),
        parse_mode="HTML",
    )
    await callback.answer()


# ─────────────────────────────────────────────
# YORDAMCHI
# ─────────────────────────────────────────────

def _format_stats(stats: dict, title: str) -> str:
    """Statistika ma'lumotlarini formatlaydi."""
    win_rate = calc_win_rate(
        int(stats.get("win_days") or 0),
        int(stats.get("completed_days") or 0),
    )
    avg_pnl = calc_average_pnl(
        float(stats.get("total_net_pnl") or 0),
        int(stats.get("completed_days") or 0),
    )

    return (
        f"📊 <b>{title}</b>\n"
        f"{'─' * 20}\n"
        f"📅 Jami kunlar: {stats.get('total_days', 0)}\n"
        f"✅ Yakunlangan: {stats.get('completed_days', 0)}\n"
        f"🎯 Win rate: {win_rate}%\n"
        f"  ✅ Maqsad bajarildi: {stats.get('win_days', 0)} kun\n"
        f"  ❌ Bajarilmadi: {stats.get('loss_days', 0)} kun\n\n"
        f"💰 Jami net PnL: <b>{format_money(float(stats.get('total_net_pnl') or 0))}</b>\n"
        f"🎯 Jami maqsad: {format_money(float(stats.get('total_target') or 0))}\n"
        f"📈 O'rtacha kunlik: {format_money(avg_pnl)}\n"
        f"🏆 Eng yaxshi kun: {format_money(float(stats.get('best_day_pnl') or 0))}\n"
        f"📉 Eng yomon kun: {format_money(float(stats.get('worst_day_pnl') or 0))}"
    )


async def _show_stats(callback: CallbackQuery, user_id: int, date_from: date, date_to: date, title: str, chart_cb: str) -> None:
    """Statistikani hisoblaydi va ko'rsatadi."""
    stats = await get_stats(user_id, date_from, date_to)
    text = _format_stats(stats, title)
    await callback.message.edit_text(
        text,
        reply_markup=stats_result_kb(chart_cb),
        parse_mode="HTML",
    )


# ─────────────────────────────────────────────
# KUNLIK / HAFTALIK / OYLIK
# ─────────────────────────────────────────────

@router.callback_query(F.data == "stats_daily")
async def stats_daily(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Bugungi statistika."""
    try:
        settings = await get_settings(user_id)
        today = get_current_date(settings["timezone"] if settings else "Asia/Tashkent")
        await _show_stats(callback, user_id, today, today, "Bugungi statistika", "chart_daily")
    except Exception as e:
        logger.error(f"stats_daily xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


@router.callback_query(F.data == "stats_weekly")
async def stats_weekly(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Haftalik statistika (oxirgi 7 kun)."""
    try:
        settings = await get_settings(user_id)
        today = get_current_date(settings["timezone"] if settings else "Asia/Tashkent")
        date_from = today - timedelta(days=6)
        await _show_stats(callback, user_id, date_from, today, "Haftalik statistika", "chart_weekly")
    except Exception as e:
        logger.error(f"stats_weekly xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


@router.callback_query(F.data == "stats_monthly")
async def stats_monthly(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Oylik statistika (joriy oy)."""
    try:
        settings = await get_settings(user_id)
        today = get_current_date(settings["timezone"] if settings else "Asia/Tashkent")
        date_from = today.replace(day=1)
        await _show_stats(callback, user_id, date_from, today, "Oylik statistika", "chart_monthly")
    except Exception as e:
        logger.error(f"stats_monthly xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


# ─────────────────────────────────────────────
# STRATEGIYA DAVRI
# ─────────────────────────────────────────────

@router.callback_query(F.data == "stats_strategy")
async def stats_strategy(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Strategiya davri statistikasi."""
    try:
        settings = await get_settings(user_id)
        if not settings or not settings.get("start_date"):
            await callback.answer("Strategiya boshlanmagan.", show_alert=True)
            return

        start_date = parse_start_date(settings["start_date"])
        today = get_current_date(settings["timezone"])
        await _show_stats(callback, user_id, start_date, today, "Strategiya davri", "chart_strategy")
    except Exception as e:
        logger.error(f"stats_strategy xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


# ─────────────────────────────────────────────
# MUDDATNI TANLASH (FSM)
# ─────────────────────────────────────────────

@router.callback_query(F.data == "stats_range")
async def stats_range_start(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """Muddatni tanlash boshlash."""
    await state.set_state(StatsRangeForm.date_from)
    await callback.message.edit_text(
        "📅 Boshlang'ich sanani kiriting (DD.MM.YYYY):",
        reply_markup=stats_cancel_kb(),
    )
    await callback.answer()


@router.message(StatsRangeForm.date_from)
async def stats_range_from(message: Message, state: FSMContext, **kwargs) -> None:
    """Boshlang'ich sana kiritildi."""
    d = _parse_date(message.text.strip())
    if not d:
        await message.answer("⚠️ Noto'g'ri format. DD.MM.YYYY ko'rinishida kiriting:", reply_markup=stats_cancel_kb())
        return
    await state.update_data(date_from=d)
    await state.set_state(StatsRangeForm.date_to)
    await message.answer(
        f"✅ Boshlang'ich: {format_date(d)}\n\nYakuniy sanani kiriting (DD.MM.YYYY):",
        reply_markup=stats_cancel_kb(),
    )


@router.message(StatsRangeForm.date_to)
async def stats_range_to(message: Message, state: FSMContext, user_id: int, **kwargs) -> None:
    """Yakuniy sana kiritildi — statistikani ko'rsatish."""
    d = _parse_date(message.text.strip())
    if not d:
        await message.answer("⚠️ Noto'g'ri format. DD.MM.YYYY ko'rinishida kiriting:", reply_markup=stats_cancel_kb())
        return

    data = await state.get_data()
    date_from = data.get("date_from")
    await state.clear()

    if d < date_from:
        await message.answer("⚠️ Yakuniy sana boshlang'ichdan katta bo'lishi kerak.")
        return

    try:
        stats = await get_stats(user_id, date_from, d)
        title = f"{format_date(date_from)} — {format_date(d)}"
        text = _format_stats(stats, title)

        # Grafik uchun davr state ga saqlanadi
        await state.update_data(chart_from=date_from, chart_to=d)

        await message.answer(
            text,
            reply_markup=stats_result_kb("chart_range"),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"stats_range_to xato [user_id={user_id}]: {e}")
        await message.answer("⚠️ Xato yuz berdi.")


def _parse_date(text: str):
    """DD.MM.YYYY → date obyekti."""
    from datetime import datetime
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except Exception:
        return None


# ─────────────────────────────────────────────
# GRAFIKLAR
# ─────────────────────────────────────────────

async def _send_chart(callback: CallbackQuery, user_id: int, date_from: date, date_to: date, title: str) -> None:
    """Grafik rasmini yaratib yuboradi."""
    journals = await get_journal_range(user_id, date_from, date_to)
    settings = await get_settings(user_id)

    if not journals:
        await callback.answer("Ma'lumot topilmadi.", show_alert=True)
        return

    dates = [j["date"] for j in journals]
    actual_balances = []
    pnl_values = []
    targets = []
    planned_balances = []

    start_bal        = float(settings["starting_balance"] or 0)
    rate             = float(settings["daily_profit_rate"] or 0.1)
    extra            = float(settings.get("extra_target") or 0)
    withdrawal_amt   = float(settings.get("withdrawal_amount") or 0)
    withdrawal_every = int(settings.get("withdrawal_every") or 0)

    for j in journals:
        actual_balances.append(float(j["end_balance"] or j["start_balance"]))
        pnl_values.append(float(j["net_pnl"] or 0))
        targets.append(float(j["target_profit"]) + float(j["extra_target"]) + float(j["carry_over_amount"]))
        planned_balances.append(calc_planned_balance(
            start_bal, rate, j["day_number"], extra, withdrawal_amt, withdrawal_every
        ))

    img_bytes = create_balance_chart(dates, actual_balances, planned_balances, title)
    if not img_bytes:
        await callback.answer("Grafik yaratishda xato.", show_alert=True)
        return

    photo = BufferedInputFile(img_bytes, filename="chart.png")
    await callback.message.answer_photo(photo, caption=f"📊 {title}")
    await callback.answer()


@router.callback_query(F.data == "chart_daily")
async def chart_daily(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    settings = await get_settings(user_id)
    today = get_current_date(settings["timezone"])
    await _send_chart(callback, user_id, today, today, "Bugungi PnL")


@router.callback_query(F.data == "chart_weekly")
async def chart_weekly(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    settings = await get_settings(user_id)
    today = get_current_date(settings["timezone"])
    await _send_chart(callback, user_id, today - timedelta(days=6), today, "Haftalik balans")


@router.callback_query(F.data == "chart_monthly")
async def chart_monthly(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    settings = await get_settings(user_id)
    today = get_current_date(settings["timezone"])
    await _send_chart(callback, user_id, today.replace(day=1), today, "Oylik balans")


@router.callback_query(F.data == "chart_strategy")
async def chart_strategy(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    settings = await get_settings(user_id)
    if not settings or not settings.get("start_date"):
        await callback.answer("Strategiya boshlanmagan.", show_alert=True)
        return
    start_date = parse_start_date(settings["start_date"])
    today = get_current_date(settings["timezone"])
    await _send_chart(callback, user_id, start_date, today, "Strategiya davri balans")


@router.callback_query(F.data == "chart_range")
async def chart_range(callback: CallbackQuery, state: FSMContext, user_id: int, **kwargs) -> None:
    """Tanlangan muddat grafigi."""
    try:
        data = await state.get_data()
        date_from = data.get("chart_from")
        date_to = data.get("chart_to")

        if not date_from or not date_to:
            await callback.answer("Davr topilmadi. Qaytadan tanlang.", show_alert=True)
            return

        title = f"{format_date(date_from)} — {format_date(date_to)}"
        await _send_chart(callback, user_id, date_from, date_to, title)
    except Exception as e:
        logger.error(f"chart_range xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
