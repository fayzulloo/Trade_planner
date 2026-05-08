"""
Savdo kiritish handlerlari.
1-usul: Qo'lda kiritish (FSM)
2-usul: MT5 Screenshot (Gemini tahlili)
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.queries import get_settings, get_today_journal, add_trade
from handlers.keyboards import (
    direction_kb, cancel_trade_kb,
    mt5_trades_list_kb, mt5_edit_fields_kb, mt5_after_edit_kb,
    plan_kb, skip_kb, trade_result_kb,
)
from utils.calculator import get_current_date, parse_start_date, get_day_number
from utils.mt5_analyzer import analyze_mt5_screenshot

logger = logging.getLogger(__name__)
router = Router()


# ─────────────────────────────────────────────
# FSM States
# ─────────────────────────────────────────────

class TradeForm(StatesGroup):
    """Qo'lda savdo kiritish bosqichlari."""
    symbol    = State()
    direction = State()
    entry     = State()
    exit      = State()
    quantity  = State()
    pnl       = State()
    sl        = State()
    tp        = State()
    result    = State()


class MT5EditForm(StatesGroup):
    """MT5 savdo maydonini tahrirlash."""
    waiting_value = State()


# ─────────────────────────────────────────────
# YORDAMCHI
# ─────────────────────────────────────────────

async def _get_day_number(user_id: int) -> int | None:
    """
    Bugungi kun raqamini qaytaradi.
    """
    settings = await get_settings(user_id)
    if not settings or not settings["is_active"]:
        return None
    start_date = parse_start_date(settings.get("start_date") or "")
    if not start_date:
        return None
    today = get_current_date(settings["timezone"])
    return get_day_number(
        start_date, today,
        settings.get("rest_days", ""),
        settings.get("total_days", 0),
    )


# ─────────────────────────────────────────────
# QO'LDA KIRITISH
# ─────────────────────────────────────────────

@router.callback_query(F.data == "trade_add")
async def trade_add_start(callback: CallbackQuery, state: FSMContext, user_id: int, **kwargs) -> None:
    """Savdo kiritishni boshlash."""
    try:
        day_number = await _get_day_number(user_id)
        if not day_number:
            await callback.answer("Bugun savdo kuni emas.", show_alert=True)
            return

        settings = await get_settings(user_id)
        today = get_current_date(settings["timezone"])
        journal = await get_today_journal(user_id, today)

        if journal and journal["is_completed"]:
            await callback.answer("⚠️ Kun allaqachon yakunlangan.", show_alert=True)
            return

        await state.set_state(TradeForm.symbol)
        await callback.message.answer(
            "📝 <b>Yangi savdo</b>\n\nSymbol kiriting (masalan: XAUUSD):",
            reply_markup=cancel_trade_kb(),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"trade_add_start xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


@router.message(TradeForm.symbol)
async def trade_symbol(message: Message, state: FSMContext, **kwargs) -> None:
    """Symbol kiritildi."""
    symbol = message.text.strip().upper()
    if len(symbol) < 3 or len(symbol) > 12:
        await message.answer("⚠️ Noto'g'ri symbol. Qaytadan kiriting:", reply_markup=cancel_trade_kb())
        return
    await state.update_data(symbol=symbol)
    await state.set_state(TradeForm.direction)
    await message.answer(
        f"✅ Symbol: <b>{symbol}</b>\n\nYo'nalish tanlang:",
        reply_markup=direction_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.in_({"dir_BUY", "dir_SELL"}))
async def trade_direction(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """BUY yoki SELL tanlandi."""
    current_state = await state.get_state()
    if current_state != TradeForm.direction:
        await callback.answer()
        return

    direction = "BUY" if callback.data == "dir_BUY" else "SELL"
    await state.update_data(direction=direction)
    await state.set_state(TradeForm.entry)
    icon = "📈" if direction == "BUY" else "📉"
    await callback.message.edit_text(
        f"{icon} Yo'nalish: <b>{direction}</b>\n\nEntry narx kiriting:",
        reply_markup=cancel_trade_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TradeForm.entry)
async def trade_entry(message: Message, state: FSMContext, **kwargs) -> None:
    """Entry narx kiritildi."""
    try:
        entry = float(message.text.replace(",", "."))
        await state.update_data(entry_price=entry)
        await state.set_state(TradeForm.exit)
        await message.answer(
            f"✅ Entry: <b>{entry}</b>\n\nExit narx kiriting:",
            reply_markup=cancel_trade_kb(),
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("⚠️ Raqam kiriting (masalan: 2345.67):", reply_markup=cancel_trade_kb())


@router.message(TradeForm.exit)
async def trade_exit(message: Message, state: FSMContext, **kwargs) -> None:
    """Exit narx kiritildi."""
    try:
        exit_price = float(message.text.replace(",", "."))
        await state.update_data(exit_price=exit_price)
        await state.set_state(TradeForm.quantity)
        await message.answer(
            f"✅ Exit: <b>{exit_price}</b>\n\nHajm (lot) kiriting:",
            reply_markup=cancel_trade_kb(),
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("⚠️ Raqam kiriting (masalan: 0.10):", reply_markup=cancel_trade_kb())


@router.message(TradeForm.quantity)
async def trade_quantity(message: Message, state: FSMContext, **kwargs) -> None:
    """Lot hajmi kiritildi."""
    try:
        qty = float(message.text.replace(",", "."))
        if qty <= 0:
            raise ValueError
        await state.update_data(quantity=qty)
        await state.set_state(TradeForm.pnl)
        await message.answer(
            f"✅ Lot: <b>{qty}</b>\n\nPnL kiriting (+/- $, masalan: +125.50):",
            reply_markup=cancel_trade_kb(),
            parse_mode="HTML",
        )
    except ValueError:
        await message.answer("⚠️ Musbat raqam kiriting (masalan: 0.10):", reply_markup=cancel_trade_kb())


@router.message(TradeForm.pnl)
async def trade_pnl(message: Message, state: FSMContext, **kwargs) -> None:
    """PnL kiritildi — SL ga o'tish."""
    try:
        pnl = float(message.text.replace(",", ".").replace("+", ""))
    except ValueError:
        await message.answer("⚠️ Raqam kiriting (masalan: +125.50 yoki -30.00):", reply_markup=cancel_trade_kb())
        return

    await state.update_data(pnl=pnl)
    await state.set_state(TradeForm.sl)
    await message.answer(
        f"✅ PnL: <b>{pnl:+.2f}$</b>\n\n"
        f"Stop Loss narxini kiriting (yo'q bo'lsa — kiritmang):",
        reply_markup=skip_kb(),
        parse_mode="HTML",
    )


@router.message(TradeForm.sl)
async def trade_sl(message: Message, state: FSMContext, **kwargs) -> None:
    """SL kiritildi."""
    text = message.text.strip()
    sl_price = None
    if text and text.lower() not in ("-", "0", "yo'q", "yoq"):
        try:
            sl_price = float(text.replace(",", "."))
        except ValueError:
            await message.answer("⚠️ Raqam kiriting yoki o'tkazib yuboring:", reply_markup=skip_kb())
            return

    await state.update_data(sl_price=sl_price)
    await state.set_state(TradeForm.tp)
    await message.answer(
        f"✅ SL: <b>{sl_price or 'yo\'q'}</b>\n\n"
        f"Take Profit narxini kiriting (yo'q bo'lsa — kiritmang):",
        reply_markup=skip_kb(),
        parse_mode="HTML",
    )


@router.message(TradeForm.tp)
async def trade_tp(message: Message, state: FSMContext, **kwargs) -> None:
    """TP kiritildi."""
    text = message.text.strip()
    tp_price = None
    if text and text.lower() not in ("-", "0", "yo'q", "yoq"):
        try:
            tp_price = float(text.replace(",", "."))
        except ValueError:
            await message.answer("⚠️ Raqam kiriting yoki o'tkazib yuboring:", reply_markup=skip_kb())
            return

    await state.update_data(tp_price=tp_price)
    await state.set_state(TradeForm.result)
    await message.answer(
        f"✅ TP: <b>{tp_price or 'yo\'q'}</b>\n\n"
        f"Savdo natijasini tanlang:",
        reply_markup=trade_result_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.in_({"result_tp", "result_sl", "result_manual"}))
async def trade_result(callback: CallbackQuery, state: FSMContext, user_id: int, **kwargs) -> None:
    """Natija tanlandi — savdoni saqlash."""
    current_state = await state.get_state()
    if current_state != TradeForm.result:
        await callback.answer()
        return

    result_map = {"result_tp": "tp", "result_sl": "sl", "result_manual": "manual"}
    result = result_map[callback.data]

    data = await state.get_data()
    await state.clear()

    try:
        day_number = await _get_day_number(user_id)
        if not day_number:
            await callback.message.answer("⚠️ Kun raqami topilmadi.")
            return

        settings = await get_settings(user_id)
        pnl = data["pnl"]
        trade = await add_trade(
            user_id=user_id,
            day_number=day_number,
            symbol=data["symbol"],
            direction=data["direction"],
            entry_price=data["entry_price"],
            exit_price=data["exit_price"],
            quantity=data["quantity"],
            pnl=pnl,
            broker=settings.get("broker_name"),
            sl_price=data.get("sl_price"),
            tp_price=data.get("tp_price"),
            result=result,
        )

        result_icons = {"tp": "🟢 TP", "sl": "🔴 SL", "manual": "⚪ Manual"}
        await callback.message.edit_text(
            f"✅ <b>Savdo saqlandi!</b>\n\n"
            f"📌 {data['symbol']} {data['direction']}\n"
            f"📊 PnL: <b>{pnl:+.2f}$</b>\n"
            f"📍 Natija: {result_icons[result]}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"trade_result saqlash xato [user_id={user_id}]: {e}")
        await callback.message.answer("⚠️ Saqlashda xato yuz berdi.")
    finally:
        await callback.answer()


@router.callback_query(F.data == "skip_field")
async def skip_field(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """SL yoki TP o'tkazib yuborish."""
    current_state = await state.get_state()

    if current_state == TradeForm.sl:
        await state.update_data(sl_price=None)
        await state.set_state(TradeForm.tp)
        await callback.message.edit_text(
            "⏭ SL o'tkazib yuborildi.\n\nTake Profit narxini kiriting:",
            reply_markup=skip_kb(),
            parse_mode="HTML",
        )
    elif current_state == TradeForm.tp:
        await state.update_data(tp_price=None)
        await state.set_state(TradeForm.result)
        await callback.message.edit_text(
            "⏭ TP o'tkazib yuborildi.\n\nSavdo natijasini tanlang:",
            reply_markup=trade_result_kb(),
            parse_mode="HTML",
        )

    await callback.answer()


@router.callback_query(F.data == "trade_cancel")
async def trade_cancel(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """Savdo kiritishni bekor qilish."""
    await state.clear()
    await callback.message.edit_text("❌ Savdo kiritish bekor qilindi.")
    await callback.answer()


# ─────────────────────────────────────────────
# MT5 SCREENSHOT
# ─────────────────────────────────────────────

@router.message(F.photo)
async def handle_mt5_screenshot(message: Message, state: FSMContext, user_id: int, **kwargs) -> None:
    """
    Rasm yuborilganda MT5 tahlili.
    Gemini API orqali savdolarni aniqlaydi.
    """
    try:
        # Eng katta o'lchamdagi rasmni olish
        photo: PhotoSize = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        wait_msg = await message.answer("⏳ Rasm tahlil qilinmoqda...")

        trades = await analyze_mt5_screenshot(image_bytes)

        await wait_msg.delete()

        if trades is None:
            await message.answer("⚠️ MT5 tahlil xizmati mavjud emas yoki xato yuz berdi.")
            return

        if not trades:
            await message.answer("❌ Rasmda savdo topilmadi.")
            return

        # State ga saqlash
        await state.update_data(mt5_trades=trades)

        # Savdolar ro'yxatini ko'rsatish
        text = f"📸 <b>{len(trades)} ta savdo topildi:</b>\n\n"
        for i, t in enumerate(trades, 1):
            sign = "+" if t["pnl"] >= 0 else ""
            text += f"{i}. {t['symbol']} {t['direction']} {sign}{t['pnl']:.2f}$\n"

        await message.answer(
            text,
            reply_markup=mt5_trades_list_kb(trades),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"handle_mt5_screenshot xato [user_id={user_id}]: {e}")
        await message.answer("⚠️ Rasmni qayta ishlashda xato yuz berdi.")


@router.callback_query(F.data.startswith("mt5_edit_"))
async def mt5_edit_trade(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """MT5 savdoni tahrirlash — maydon tanlash."""
    idx = int(callback.data.split("_")[-1])
    data = await state.get_data()
    trades = data.get("mt5_trades", [])

    if idx >= len(trades):
        await callback.answer("Savdo topilmadi.", show_alert=True)
        return

    t = trades[idx]
    sign = "+" if t["pnl"] >= 0 else ""
    await callback.message.edit_text(
        f"✏️ <b>{idx+1}. {t['symbol']} {t['direction']}</b>\n"
        f"Entry: {t['entry_price']} | Exit: {t['exit_price']}\n"
        f"Lot: {t['quantity']} | PnL: {sign}{t['pnl']:.2f}$\n\n"
        f"Qaysi maydonni tahrirlaysiz?",
        reply_markup=mt5_edit_fields_kb(idx),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mt5ef_"))
async def mt5_edit_field(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """MT5 aniq maydonni tahrirlash."""
    parts = callback.data.split("_", 2)  # mt5ef_{idx}_{field}
    idx = int(parts[1])
    field = parts[2]

    field_names = {
        "symbol": "Symbol (masalan: XAUUSD)",
        "direction": "Yo'nalish (BUY yoki SELL)",
        "entry_price": "Entry narx",
        "exit_price": "Exit narx",
        "quantity": "Lot hajmi",
        "pnl": "PnL (masalan: +125.50 yoki -30.00)",
        "open_time": "Kirish vaqti (masalan: 2024.01.15 10:30)",
        "close_time": "Chiqish vaqti (masalan: 2024.01.15 14:45)",
    }

    await state.set_state(MT5EditForm.waiting_value)
    await state.update_data(editing_idx=idx, editing_field=field)
    await callback.message.edit_text(
        f"✏️ <b>{field_names.get(field, field)}</b> kiriting:",
        reply_markup=cancel_trade_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(MT5EditForm.waiting_value)
async def mt5_save_field(message: Message, state: FSMContext, **kwargs) -> None:
    """MT5 maydon qiymati kiritildi — saqlash."""
    data = await state.get_data()
    idx = data.get("editing_idx", 0)
    field = data.get("editing_field", "")
    trades = data.get("mt5_trades", [])

    if idx >= len(trades):
        await state.clear()
        await message.answer("⚠️ Savdo topilmadi.")
        return

    value = message.text.strip()

    # Tip konversiyasi
    try:
        if field in ("entry_price", "exit_price", "quantity"):
            value = float(value.replace(",", "."))
        elif field in ("pnl", "swap", "commission"):
            value = float(value.replace(",", ".").replace("+", ""))
        elif field == "direction":
            value = value.upper()
            if value not in ("BUY", "SELL"):
                await message.answer("⚠️ Faqat BUY yoki SELL kiriting:", reply_markup=cancel_trade_kb())
                return
        elif field == "symbol":
            value = value.upper()
    except ValueError:
        await message.answer("⚠️ Noto'g'ri qiymat. Raqam kiriting:", reply_markup=cancel_trade_kb())
        return

    trades[idx][field] = value
    await state.update_data(mt5_trades=trades, editing_idx=None, editing_field=None)
    await state.set_state(None)

    await message.answer(
        f"✅ <b>Qabul qilindi!</b>",
        reply_markup=mt5_after_edit_kb(idx),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "mt5_back_to_list")
async def mt5_back_to_list(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """MT5 ro'yxatga qaytish."""
    data = await state.get_data()
    trades = data.get("mt5_trades", [])
    text = f"📸 <b>{len(trades)} ta savdo:</b>\n\n"
    for i, t in enumerate(trades, 1):
        sign = "+" if t["pnl"] >= 0 else ""
        text += f"{i}. {t['symbol']} {t['direction']} {sign}{t['pnl']:.2f}$\n"
    await callback.message.edit_text(
        text,
        reply_markup=mt5_trades_list_kb(trades),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "mt5_save_all")
async def mt5_save_all(callback: CallbackQuery, state: FSMContext, user_id: int, **kwargs) -> None:
    """MT5 barcha savdolarni saqlash."""
    try:
        data = await state.get_data()
        trades = data.get("mt5_trades", [])
        await state.clear()

        day_number = await _get_day_number(user_id)
        if not day_number:
            await callback.answer("Bugun savdo kuni emas.", show_alert=True)
            return

        settings = await get_settings(user_id)
        saved = 0
        for t in trades:
            try:
                await add_trade(
                    user_id=user_id,
                    day_number=day_number,
                    symbol=t["symbol"],
                    direction=t["direction"],
                    entry_price=t.get("entry_price", 0),
                    exit_price=t.get("exit_price", 0),
                    quantity=t.get("quantity", 0),
                    pnl=t.get("pnl", 0),
                    swap=t.get("swap", 0),
                    commission=t.get("commission", 0),
                    open_time=t.get("open_time"),
                    close_time=t.get("close_time"),
                    order_id=t.get("order_id"),
                    broker=settings.get("broker_name"),
                    sl_price=t.get("sl_price"),
                    tp_price=t.get("tp_price"),
                    result=t.get("result"),
                )
                saved += 1
            except Exception as e:
                logger.error(f"MT5 savdo saqlash xato: {e}")

        await callback.message.edit_text(
            f"✅ <b>{saved} ta savdo saqlandi!</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"mt5_save_all xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


@router.callback_query(F.data == "mt5_cancel")
async def mt5_cancel(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """MT5 kiritishni bekor qilish."""
    await state.clear()
    await callback.message.edit_text("❌ MT5 kiritish bekor qilindi.")
    await callback.answer()
