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
    if not message.text:
        await message.answer("⚠️ Iltimos matn kiriting:", reply_markup=cancel_keyboard(), parse_mode="HTML")
        return
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
    if not message.text:
        await message.answer("⚠️ Raqam kiriting:", reply_markup=cancel_keyboard(), parse_mode="HTML")
        return
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
    if not message.text:
        await message.answer("⚠️ Raqam kiriting:", reply_markup=cancel_keyboard(), parse_mode="HTML")
        return
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



# ===== MT5 SKRINSHOT =====

class MT5EditForm(StatesGroup):
    editing_field = State()
    editing_idx = State()


def _trade_text(idx: int, t: dict) -> str:
    pnl = t.get("pnl")
    pnl_sign = t.get("pnl_sign", 1)  # +1 foyda, -1 zarar

    if pnl is not None:
        display_pnl = abs(float(pnl)) * pnl_sign
        sign_str = "+" if display_pnl >= 0 else ""
        pnl_str = f"{sign_str}{display_pnl:.2f}$"
        emoji = "🟢" if display_pnl >= 0 else "🔴"
    else:
        # PnL topilmadi — pnl_sign dan foydalanib ko'rsatamiz
        emoji = "🟢" if pnl_sign >= 0 else "🔴"
        pnl_str = "Noma'lum (tahrirlang)"

    swap = float(t.get("swap") or 0)
    commission = float(t.get("commission") or 0)
    order_id = t.get("order_id")

    text = (
        f"<b>{idx + 1}. {t.get('symbol', '?')} {t.get('direction', '?')} "
        f"{t.get('quantity', '?')} lot</b>\n"
        f"   📥 Kirish: <b>{t.get('entry_price', '?')}</b>\n"
        f"   📤 Chiqish: <b>{t.get('exit_price', '?')}</b>\n"
        f"   🕐 Ochilgan: <b>{t.get('open_time') or '—'}</b>\n"
        f"   🕑 Yopilgan: <b>{t.get('close_time') or '—'}</b>\n"
        f"   {emoji} PnL: <b>{pnl_str}</b>\n"
        f"   💱 Svop: <b>{swap}</b> | Komissiya: <b>{commission}</b>"
    )
    if order_id:
        text += f"\n   🔖 Order: <b>#{order_id}</b>"
    return text


def _mt5_confirm_kb(trades: list) -> "InlineKeyboardMarkup":
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for i, t in enumerate(trades):
        rows.append([InlineKeyboardButton(
            text=f"✏️ {i+1}. {t.get('symbol','?')} {t.get('direction','?')} | {'🟢' if t.get('pnl_sign',1)>=0 else '🔴'} {abs(float(t.get('pnl') or 0)):.2f}$",
            callback_data=f"mt5_edit_{i}"
        )])
    rows.append([
        InlineKeyboardButton(text="✅ Hammasini saqlash", callback_data="mt5_save_all"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="mt5_cancel")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _mt5_edit_kb(idx: int) -> "InlineKeyboardMarkup":
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Symbol", callback_data=f"mt5ef_{idx}_symbol"),
            InlineKeyboardButton(text="Direction", callback_data=f"mt5ef_{idx}_direction"),
        ],
        [
            InlineKeyboardButton(text="Entry", callback_data=f"mt5ef_{idx}_entry_price"),
            InlineKeyboardButton(text="Exit", callback_data=f"mt5ef_{idx}_exit_price"),
        ],
        [
            InlineKeyboardButton(text="Quantity", callback_data=f"mt5ef_{idx}_quantity"),
            InlineKeyboardButton(text="PnL", callback_data=f"mt5ef_{idx}_pnl"),
        ],
        [
            InlineKeyboardButton(text="Kirish vaqti", callback_data=f"mt5ef_{idx}_open_time"),
            InlineKeyboardButton(text="Chiqish vaqti", callback_data=f"mt5ef_{idx}_close_time"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="mt5_back_to_list")],
    ])


def _build_full_text(trades: list) -> str:
    text = f"📋 <b>Aniqlangan savdolar ({len(trades)} ta):</b>\n\n"
    for i, t in enumerate(trades):
        text += _trade_text(i, t) + "\n\n"
    text += "✏️ Xato bo'lsa savdo ustidagi tugmani bosing.\n"
    text += "✅ To'g'ri bo'lsa <b>Hammasini saqlash</b> bosing."
    return text


@router.message(F.photo)
async def handle_mt5_screenshot(message: Message, state: FSMContext,
                                  db_user_id: int, settings_complete: bool):
    if not settings_complete:
        await message.answer("⚠️ Avval sozlamalarni to'ldiring.", parse_mode="HTML")
        return

    from datetime import datetime, date as date_type
    settings = await get_settings(db_user_id)
    if settings and settings.get("start_date"):
        start = datetime.strptime(settings["start_date"], "%d.%m.%Y").date()
        if start > date_type.today():
            await message.answer("⏳ Strategiya hali boshlanmagan!", parse_mode="HTML")
            return

    wait_msg = await message.answer("🔍 Skrinshot tahlil qilinmoqda...")

    try:
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        image_bytes = file_bytes.read()

        from utils.mt5_analyzer import analyze_mt5_screenshot
        trades, need_wait = await analyze_mt5_screenshot(image_bytes)

        await wait_msg.delete()

        if not trades:
            if need_wait:
                await message.answer(
                    "⏳ <b>Barcha modellar vaqtincha band.</b>"

                    "Biroz kuting va qayta urinib ko'ring."

                    "Yoki savdoni qo'lda kiriting: <b>📊 Bugungi reja → 📝 Savdo kiriting</b>",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "❌ Skrinshot tahlil qilinmadi."
                    
                    "MT5 yopilgan savdolar ekranini yuboring yoki "
                    "savdoni qo'lda kiriting.",
                    parse_mode="HTML"
                )
            return

        # Noma'lum maydonlarni tekshirish
        invalid = []
        for i, t in enumerate(trades):
            missing = [k for k, v in t.items() if v is None and k in ("symbol", "direction", "entry_price", "exit_price", "quantity", "pnl")]
            if missing:
                invalid.append(f"{i+1}-savdo: {', '.join(missing)}")

        await state.update_data(mt5_trades=trades)

        text = _build_full_text(trades)
        if invalid:
            text += "\n\n⚠️ <b>Quyidagi maydonlar o'qilmadi:</b>\n" + "\n".join(invalid)

        await message.answer(text, reply_markup=_mt5_confirm_kb(trades), parse_mode="HTML")

    except Exception as e:
        logger.error(f"MT5 skrinshot xatosi: {e}")
        try:
            await wait_msg.delete()
        except Exception:
            pass
        await message.answer("⚠️ Xato yuz berdi. Qayta urinib ko'ring.", parse_mode="HTML")


@router.callback_query(F.data == "mt5_back_to_list")
async def mt5_back_to_list(call: CallbackQuery, state: FSMContext):
    await state.set_state(None)
    data = await state.get_data()
    trades = data.get("mt5_trades", [])
    text = _build_full_text(trades)
    try:
        await call.message.edit_text(text, reply_markup=_mt5_confirm_kb(trades), parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=_mt5_confirm_kb(trades), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("mt5_edit_"))
async def mt5_edit_trade(call: CallbackQuery, state: FSMContext):
    idx = int(call.data.split("_")[2])
    data = await state.get_data()
    trades = data.get("mt5_trades", [])
    if idx >= len(trades):
        await call.answer("Savdo topilmadi!", show_alert=True)
        return

    t = trades[idx]
    text = f"✏️ <b>{idx+1}-savdoni tahrirlash:</b>\n\n" + _trade_text(idx, t) + "\n\nQaysi maydonni o'zgartirmoqchisiz?"
    try:
        await call.message.edit_text(text, reply_markup=_mt5_edit_kb(idx), parse_mode="HTML")
    except Exception:
        await call.message.answer(text, reply_markup=_mt5_edit_kb(idx), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("mt5ef_"))
async def mt5_edit_field(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    idx = int(parts[1])
    field = "_".join(parts[2:])

    field_names = {
        "symbol": "Symbol (masalan: XAUUSD)",
        "direction": "Yo'nalish: BUY yoki SELL",
        "entry_price": "Kirish narxi (masalan: 4825.546)",
        "exit_price": "Chiqish narxi (masalan: 4827.149)",
        "quantity": "Miqdor/lot (masalan: 1.00)",
        "pnl": "PnL (masalan: -160.30)",
        "open_time": "Ochilish vaqti (masalan: 2026.04.16 02:49:47)",
        "close_time": "Yopilish vaqti (masalan: 2026.04.16 03:12:00)",
    }

    await state.update_data(editing_idx=idx, editing_field=field)
    await state.set_state(MT5EditForm.editing_field)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=f"mt5_edit_{idx}")]
    ])
    await call.message.edit_text(
        f"✏️ <b>{field_names.get(field, field)}</b> ni kiriting:",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()


@router.message(MT5EditForm.editing_field)
async def mt5_save_field(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("editing_idx")
    field = data.get("editing_field")
    trades = data.get("mt5_trades", [])

    if idx is None or field is None or idx >= len(trades):
        await state.clear()
        return

    value = message.text.strip()

    try:
        if field in ("entry_price", "exit_price", "quantity"):
            trades[idx][field] = float(value.replace(",", ".").replace(" ", ""))
        elif field == "pnl":
            trades[idx][field] = float(value.replace(",", ".").replace("+", "").replace(" ", ""))
        elif field == "direction":
            v = value.upper()
            if v not in ("BUY", "SELL"):
                await message.answer("⚠️ Faqat BUY yoki SELL kiriting:")
                return
            trades[idx][field] = v
        elif field == "symbol":
            trades[idx][field] = value.upper()
        else:
            trades[idx][field] = value

        await state.update_data(mt5_trades=trades)
        await state.set_state(None)

        t = trades[idx]
        text = f"✅ Saqlandi!\n\n✏️ <b>{idx+1}-savdo:</b>\n\n" + _trade_text(idx, t) + "\n\nBoshqa maydon o'zgartirmoqchimisiz?"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Yana tahrirlash", callback_data=f"mt5_edit_{idx}")],
            [InlineKeyboardButton(text="🔙 Ro'yxatga qaytish", callback_data="mt5_back_to_list")],
        ])
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

    except ValueError:
        await message.answer("⚠️ Noto'g'ri format. Qayta kiriting:")


@router.callback_query(F.data == "mt5_save_all")
async def mt5_save_all(call: CallbackQuery, state: FSMContext, db_user_id: int):
    data = await state.get_data()
    trades = data.get("mt5_trades", [])
    await state.clear()

    if not trades:
        await call.answer("Savdo topilmadi!", show_alert=True)
        return

    settings = await get_settings(db_user_id)
    day = get_current_day(settings["start_date"], settings["total_days"])

    saved = 0
    errors = 0
    total_pnl = 0.0

    for t in trades:
        try:
            # pnl_sign dan foydalanib to'g'ri PnL hisoblash
            pnl_raw = t.get("pnl")
            pnl_sign = t.get("pnl_sign", 1)

            if pnl_raw is not None:
                pnl_final = abs(float(pnl_raw)) * pnl_sign
            else:
                # PnL kiritilmagan — 0 saqlaymiz, foydalanuvchi keyinroq tuzatadi
                pnl_final = 0.0
                logger.warning(f"PnL topilmadi: {t.get('symbol')} {t.get('direction')}")

            # Broker sozlamalardan olinadi
            broker = settings.get("broker_name") or None

            await add_trade(
                user_id=db_user_id,
                day_number=day,
                symbol=t["symbol"],
                direction=t["direction"],
                entry=float(t["entry_price"]),
                exit_p=float(t["exit_price"]),
                qty=float(t.get("quantity") or 1.0),
                pnl=round(pnl_final, 2),
                open_time=t.get("open_time"),
                close_time=t.get("close_time"),
                order_id=t.get("order_id"),
                swap=float(t.get("swap") or 0),
                commission=float(t.get("commission") or 0),
                broker=broker,
            )
            total_pnl += pnl_final
            saved += 1
        except Exception as e:
            logger.error(f"Savdo saqlashda xato: {e}, trade: {t}")
            errors += 1

    await update_journal_pnl(db_user_id)

    sign = "+" if total_pnl >= 0 else ""
    emoji = "🟢" if total_pnl >= 0 else "🔴"

    result_text = (
        f"{'✅' if not errors else '⚠️'} <b>{saved} ta savdo saqlandi"
        f"{f', {errors} ta xato' if errors else ''}!</b>\n\n"
        f"{emoji} Jami PnL: <b>{sign}{total_pnl:.2f}$</b>"
    )

    await call.message.edit_text(result_text, parse_mode="HTML")

    text, info = await build_plan_text(db_user_id)
    is_wday = info.get("is_withdrawal_day", False)
    wc = info.get("withdrawal_confirmed", False)
    remaining = info.get("remaining", 0)

    if remaining <= 0:
        await call.message.answer(
            "🎉 <b>Tabriklaymiz! Bugungi maqsadga erishdingiz!</b>",
            parse_mode="HTML"
        )

    await call.message.answer(
        text,
        reply_markup=plan_inline(is_withdrawal_day=is_wday, withdrawal_confirmed=wc),
        parse_mode="HTML"
    )
    await call.answer(f"✅ {saved} ta savdo saqlandi!")


@router.callback_query(F.data == "mt5_cancel")
async def mt5_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "❌ Bekor qilindi.\n\n"
        "Savdoni qo'lda kiritish uchun "
        "<b>📊 Bugungi reja → 📝 Savdo kiriting</b>",
        parse_mode="HTML"
    )
    await call.answer()
