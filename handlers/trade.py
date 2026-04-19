from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.queries import add_trade, get_today_journal, get_settings, update_journal_pnl
from utils.calculator import get_current_day
from handlers.keyboards import plan_inline
from handlers.plan import build_plan_text
from utils.logger import logger

router = Router()


class TradeForm(StatesGroup):
    symbol = State()
    direction = State()
    entry = State()
    exit_price = State()
    quantity = State()
    pnl = State()


def cancel_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="trade_cancel")]
    ])


@router.callback_query(F.data == "trade_add")
async def trade_start(call: CallbackQuery, state: FSMContext, db_user_id: int, settings_complete: bool):
    if not settings_complete:
        await call.answer("Sozlamalar to'ldirilmagan!", show_alert=True)
        return
    await state.set_state(TradeForm.symbol)
    await call.message.edit_text(
        "📝 <b>Yangi savdo kiritish</b>\n\n"
        "1️⃣ Juft nomini kiriting:\n"
        "<i>Masalan: EURUSD, GBPUSD, XAUUSD</i>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(TradeForm.symbol)
async def trade_symbol(message: Message, state: FSMContext):
    symbol = message.text.strip().upper()
    if len(symbol) < 3 or len(symbol) > 10:
        await message.answer(
            "⚠️ Noto'g'ri format. Qayta kiriting:\n<i>Masalan: EURUSD</i>",
            reply_markup=cancel_keyboard(), parse_mode="HTML"
        )
        return
    await state.update_data(symbol=symbol)
    await state.set_state(TradeForm.direction)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 BUY", callback_data="dir_BUY"),
            InlineKeyboardButton(text="📉 SELL", callback_data="dir_SELL")
        ],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="trade_cancel")]
    ])
    await message.answer(
        f"✅ Juft: <b>{symbol}</b>\n\n2️⃣ Yo'nalishni tanlang:",
        reply_markup=kb, parse_mode="HTML"
    )


@router.callback_query(F.data.in_(["dir_BUY", "dir_SELL"]))
async def trade_direction(call: CallbackQuery, state: FSMContext):
    direction = call.data.split("_")[1]
    await state.update_data(direction=direction)
    await state.set_state(TradeForm.entry)
    await call.message.edit_text(
        f"✅ Yo'nalish: <b>{direction}</b>\n\n3️⃣ Kirish narxini kiriting:\n<i>Masalan: 1.08523</i>",
        reply_markup=cancel_keyboard(), parse_mode="HTML"
    )
    await call.answer()


@router.message(TradeForm.entry)
async def trade_entry(message: Message, state: FSMContext):
    try:
        entry = float(message.text.replace(",", "."))
        if entry <= 0:
            raise ValueError
        await state.update_data(entry=entry)
        await state.set_state(TradeForm.exit_price)
        await message.answer(
            f"✅ Kirish narxi: <b>{entry}</b>\n\n4️⃣ Chiqish narxini kiriting:",
            reply_markup=cancel_keyboard(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri raqam. Qayta kiriting:\n<i>Masalan: 1.08523</i>",
            reply_markup=cancel_keyboard(), parse_mode="HTML"
        )


@router.message(TradeForm.exit_price)
async def trade_exit(message: Message, state: FSMContext):
    try:
        exit_p = float(message.text.replace(",", "."))
        if exit_p <= 0:
            raise ValueError
        await state.update_data(exit_price=exit_p)
        await state.set_state(TradeForm.quantity)
        await message.answer(
            f"✅ Chiqish narxi: <b>{exit_p}</b>\n\n5️⃣ Miqdorni kiriting (lot):\n<i>Masalan: 0.1</i>",
            reply_markup=cancel_keyboard(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri raqam. Qayta kiriting:",
            reply_markup=cancel_keyboard(), parse_mode="HTML"
        )


@router.message(TradeForm.quantity)
async def trade_quantity(message: Message, state: FSMContext):
    try:
        qty = float(message.text.replace(",", "."))
        if qty <= 0:
            raise ValueError
        await state.update_data(quantity=qty)
        await state.set_state(TradeForm.pnl)
        await message.answer(
            f"✅ Miqdor: <b>{qty}</b>\n\n"
            "6️⃣ PnL ni kiriting (USD):\n"
            "<i>Foyda: +25.50 yoki 25.50\n"
            "Zarar: -15.00</i>",
            reply_markup=cancel_keyboard(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri raqam. Qayta kiriting:",
            reply_markup=cancel_keyboard(), parse_mode="HTML"
        )


@router.message(TradeForm.pnl)
async def trade_pnl(message: Message, state: FSMContext, db_user_id: int):
    try:
        pnl = float(message.text.replace(",", ".").replace("+", ""))
        data = await state.get_data()
        await state.clear()

        settings = await get_settings(db_user_id)
        day = get_current_day(settings["start_date"], settings["total_days"])

        await add_trade(
            user_id=db_user_id,
            day_number=day,
            symbol=data["symbol"],
            direction=data["direction"],
            entry=data["entry"],
            exit_p=data["exit_price"],
            qty=data["quantity"],
            pnl=pnl
        )
        await update_journal_pnl(db_user_id)

        emoji = "🟢" if pnl >= 0 else "🔴"
        sign = "+" if pnl >= 0 else ""

        await message.answer(
            f"{emoji} <b>Savdo saqlandi!</b>\n\n"
            f"📌 Juft: <b>{data['symbol']}</b>\n"
            f"📊 Yo'nalish: <b>{data['direction']}</b>\n"
            f"📥 Kirish: <b>{data['entry']}</b>\n"
            f"📤 Chiqish: <b>{data['exit_price']}</b>\n"
            f"📦 Miqdor: <b>{data['quantity']}</b>\n"
            f"💵 PnL: <b>{sign}{pnl}$</b>",
            parse_mode="HTML"
        )

        text, info = await build_plan_text(db_user_id)
        is_wday = info.get("is_withdrawal_day", False)
        wc = info.get("withdrawal_confirmed", False)
        remaining = info.get("remaining", 0)

        if remaining <= 0:
            await message.answer(
                "🎉 <b>Tabriklaymiz! Bugungi maqsadga erishdingiz!</b>",
                parse_mode="HTML"
            )

        await message.answer(
            text,
            reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc),
            parse_mode="HTML"
        )

    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri raqam. Qayta kiriting:\n<i>Masalan: +25.50 yoki -10.00</i>",
            reply_markup=cancel_keyboard(), parse_mode="HTML"
        )


@router.callback_query(F.data == "trade_cancel")
async def trade_cancel(call: CallbackQuery, state: FSMContext, db_user_id: int):
    await state.clear()
    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)
    await call.message.edit_text(
        text,
        reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc),
        parse_mode="HTML"
    )
    await call.answer("❌ Bekor qilindi")
