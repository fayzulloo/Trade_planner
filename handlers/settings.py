from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.queries import get_settings, upsert_setting, activate_strategy
from handlers.keyboards import main_keyboard
from utils.logger import logger
import pytz

router = Router()

TIMEZONES = [
    "Asia/Tashkent", "Asia/Almaty", "Asia/Baku", "Asia/Tbilisi",
    "Europe/Moscow", "Europe/London", "America/New_York", "Asia/Dubai"
]


class SettingsForm(StatesGroup):
    balance = State()
    rate = State()
    extra = State()
    withdrawal = State()
    wevery = State()
    days = State()
    startdate = State()
    reminder = State()


def cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="settings_open")]
    ])


def settings_inline_kb(s: dict | None) -> InlineKeyboardMarkup:
    def val(key, default="—"):
        if not s:
            return default
        v = s.get(key)
        return v if v is not None else default

    rate_pct = int(float(val("daily_profit_rate", 0.20)) * 100)

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Boshlang'ich balans: {val('starting_balance')}$", callback_data="set_balance")],
        [InlineKeyboardButton(text=f"📊 Kunlik foiz: {rate_pct}%", callback_data="set_rate")],
        [InlineKeyboardButton(text=f"➕ Qo'shimcha maqsad: {val('extra_target', 0)}$", callback_data="set_extra")],
        [InlineKeyboardButton(text=f"💸 Yechish summasi: {val('withdrawal_amount', 0)}$", callback_data="set_withdrawal")],
        [InlineKeyboardButton(text=f"📅 Yechish davri: har {val('withdrawal_every')} kunda", callback_data="set_wevery")],
        [InlineKeyboardButton(text=f"🗓 Kun soni: {val('total_days')} kun", callback_data="set_days")],
        [InlineKeyboardButton(text=f"📆 Boshlanish: {val('start_date')}", callback_data="set_startdate")],
        [InlineKeyboardButton(text=f"🌍 Timezone: {val('timezone', 'Asia/Tashkent')}", callback_data="set_timezone")],
        [InlineKeyboardButton(text=f"⏰ Eslatma: {val('reminder_time', '08:00')}", callback_data="set_reminder")],
        [InlineKeyboardButton(text="💾 Saqlash va yopish", callback_data="settings_save")],
    ])


def _settings_text() -> str:
    return (
        "⚙️ <b>Sozlamalar</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "Quyidagi tugmalardan birini bosib o'zgartiring.\n"
        "Tugatgach <b>💾 Saqlash</b> tugmasini bosing."
    )


@router.message(F.text == "⚙️ Sozlamalar")
async def settings_handler(message: Message, db_user_id: int):
    s = await get_settings(db_user_id)
    await message.answer(
        _settings_text(),
        reply_markup=settings_inline_kb(s),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "settings_open")
async def settings_open(call: CallbackQuery, state: FSMContext, db_user_id: int):
    await state.clear()
    s = await get_settings(db_user_id)
    await call.message.edit_text(
        _settings_text(),
        reply_markup=settings_inline_kb(s),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "settings_save")
async def settings_save(call: CallbackQuery, db_user_id: int):
    """Saqlash tugmasi — inline tugmalarni o'chiradi"""
    s = await get_settings(db_user_id)
    if not s:
        await call.answer("⚠️ Hech narsa sozlanmagan!", show_alert=True)
        return

    rate_pct = int(float(s.get("daily_profit_rate") or 0.20) * 100)
    text = (
        "✅ <b>Sozlamalar saqlandi!</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"💰 Boshlang'ich balans: <b>{s.get('starting_balance') or '—'}$</b>\n"
        f"📊 Kunlik foiz: <b>{rate_pct}%</b>\n"
        f"➕ Qo'shimcha maqsad: <b>{s.get('extra_target') or 0}$</b>\n"
        f"💸 Yechish summasi: <b>{s.get('withdrawal_amount') or 0}$</b>\n"
        f"📅 Yechish davri: <b>har {s.get('withdrawal_every') or '—'} kunda</b>\n"
        f"🗓 Kun soni: <b>{s.get('total_days') or '—'} kun</b>\n"
        f"📆 Boshlanish: <b>{s.get('start_date') or '—'}</b>\n"
        f"🌍 Timezone: <b>{s.get('timezone') or 'Asia/Tashkent'}</b>\n"
        f"⏰ Eslatma: <b>{s.get('reminder_time') or '08:00'}</b>\n"
    )
    # Inline tugmalarni o'chiramiz
    await call.message.edit_text(text, reply_markup=None, parse_mode="HTML")
    await call.answer("✅ Saqlandi!")
    logger.info(f"Sozlamalar saqlandi: user_id={db_user_id}")


# ===== BALANCE =====
@router.callback_query(F.data == "set_balance")
async def ask_balance(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.balance)
    await call.message.edit_text(
        "💰 Boshlang'ich balans kiriting (USD):\n<i>Masalan: 100</i>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsForm.balance)
async def save_balance(message: Message, state: FSMContext, db_user_id: int):
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0:
            raise ValueError
        await upsert_setting(db_user_id, "starting_balance", val)
        await state.clear()
        s = await get_settings(db_user_id)
        await message.answer(
            _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ Noto'g'ri raqam. Qayta kiriting:", reply_markup=cancel_kb(), parse_mode="HTML")


# ===== RATE =====
@router.callback_query(F.data == "set_rate")
async def ask_rate(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.rate)
    await call.message.edit_text(
        "📊 Kunlik foiz kiriting (%):\n<i>Masalan: 13</i>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsForm.rate)
async def save_rate(message: Message, state: FSMContext, db_user_id: int):
    try:
        val = float(message.text.replace(",", ".").replace("%", ""))
        if val <= 0 or val > 100:
            raise ValueError
        await upsert_setting(db_user_id, "daily_profit_rate", val / 100)
        await state.clear()
        s = await get_settings(db_user_id)
        await message.answer(
            _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ 1 dan 100 gacha raqam kiriting:", reply_markup=cancel_kb(), parse_mode="HTML")


# ===== EXTRA =====
@router.callback_query(F.data == "set_extra")
async def ask_extra(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.extra)
    await call.message.edit_text(
        "➕ Qo'shimcha kunlik maqsad kiriting (USD):\n<i>Masalan: 10</i>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsForm.extra)
async def save_extra(message: Message, state: FSMContext, db_user_id: int):
    try:
        val = float(message.text.replace(",", "."))
        if val < 0:
            raise ValueError
        await upsert_setting(db_user_id, "extra_target", val)
        await state.clear()
        s = await get_settings(db_user_id)
        await message.answer(
            _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ Noto'g'ri raqam. Qayta kiriting:", reply_markup=cancel_kb(), parse_mode="HTML")


# ===== WITHDRAWAL =====
@router.callback_query(F.data == "set_withdrawal")
async def ask_withdrawal(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.withdrawal)
    await call.message.edit_text(
        "💸 Yechish summasi kiriting (USD):\n<i>0 kiritsangiz yechish bo'lmaydi</i>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsForm.withdrawal)
async def save_withdrawal(message: Message, state: FSMContext, db_user_id: int):
    try:
        val = float(message.text.replace(",", "."))
        if val < 0:
            raise ValueError
        await upsert_setting(db_user_id, "withdrawal_amount", val)
        await state.clear()
        s = await get_settings(db_user_id)
        await message.answer(
            _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ Noto'g'ri raqam. Qayta kiriting:", reply_markup=cancel_kb(), parse_mode="HTML")


# ===== WITHDRAWAL EVERY =====
@router.callback_query(F.data == "set_wevery")
async def ask_wevery(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.wevery)
    await call.message.edit_text(
        "📅 Har necha ish kunida yechish?\n<i>Masalan: 5 (har 5 ish kunda)</i>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsForm.wevery)
async def save_wevery(message: Message, state: FSMContext, db_user_id: int):
    try:
        val = int(message.text.strip())
        if val <= 0:
            raise ValueError
        await upsert_setting(db_user_id, "withdrawal_every", val)
        await state.clear()
        s = await get_settings(db_user_id)
        await message.answer(
            _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ Musbat butun son kiriting:", reply_markup=cancel_kb(), parse_mode="HTML")


# ===== DAYS =====
@router.callback_query(F.data == "set_days")
async def ask_days(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.days)
    await call.message.edit_text(
        "🗓 Strategiya ish kunlari sonini kiriting:\n<i>Masalan: 60 (shanba/yakshanba hisoblanmaydi)</i>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsForm.days)
async def save_days(message: Message, state: FSMContext, db_user_id: int):
    try:
        val = int(message.text.strip())
        if val <= 0:
            raise ValueError
        await upsert_setting(db_user_id, "total_days", val)
        await state.clear()
        s = await get_settings(db_user_id)
        await message.answer(
            _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
        )
    except ValueError:
        await message.answer("⚠️ Musbat butun son kiriting:", reply_markup=cancel_kb(), parse_mode="HTML")


# ===== START DATE =====
@router.callback_query(F.data == "set_startdate")
async def ask_startdate(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.startdate)
    await call.message.edit_text(
        "📆 Boshlanish sanasini kiriting:\n<i>Format: 01.11.2025</i>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsForm.startdate)
async def save_startdate(message: Message, state: FSMContext, db_user_id: int):
    try:
        from datetime import datetime
        datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await upsert_setting(db_user_id, "start_date", message.text.strip())
        await activate_strategy(db_user_id)
        await state.clear()
        s = await get_settings(db_user_id)
        await message.answer(
            _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Format noto'g'ri. Qayta kiriting:\n<i>Masalan: 01.11.2025</i>",
            reply_markup=cancel_kb(), parse_mode="HTML"
        )


# ===== TIMEZONE =====
@router.callback_query(F.data == "set_timezone")
async def ask_timezone(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tz, callback_data=f"tz_{tz}")] for tz in TIMEZONES
    ] + [[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="settings_open")]])
    await call.message.edit_text("🌍 Timezoneni tanlang:", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("tz_"))
async def save_timezone(call: CallbackQuery, db_user_id: int):
    tz = call.data[3:]
    await upsert_setting(db_user_id, "timezone", tz)
    s = await get_settings(db_user_id)
    await call.message.edit_text(
        _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
    )
    await call.answer(f"✅ {tz} saqlandi")


# ===== REMINDER =====
@router.callback_query(F.data == "set_reminder")
async def ask_reminder(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.reminder)
    await call.message.edit_text(
        "⏰ Eslatma vaqtini kiriting:\n<i>Format: 08:00</i>",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsForm.reminder)
async def save_reminder(message: Message, state: FSMContext, db_user_id: int):
    try:
        from datetime import datetime
        datetime.strptime(message.text.strip(), "%H:%M")
        await upsert_setting(db_user_id, "reminder_time", message.text.strip())
        await state.clear()
        s = await get_settings(db_user_id)
        await message.answer(
            _settings_text(), reply_markup=settings_inline_kb(s), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Format noto'g'ri. Qayta kiriting:\n<i>Masalan: 08:00</i>",
            reply_markup=cancel_kb(), parse_mode="HTML"
        )
