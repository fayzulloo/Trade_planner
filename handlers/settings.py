from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.queries import get_settings, upsert_setting, activate_strategy
from handlers.keyboards import settings_inline, back_inline, main_keyboard
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
    timezone = State()
    reminder = State()


def cancel_kb():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="settings_back")]
    ])


@router.message(F.text == "⚙️ Sozlamalar")
async def settings_handler(message: Message, db_user_id: int):
    s = await get_settings(db_user_id)
    text = _settings_text(s)
    await message.answer(text, reply_markup=settings_inline(), parse_mode="HTML")


def _settings_text(s: dict | None) -> str:
    if not s:
        return (
            "⚙️ <b>Sozlamalar</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "Hali hech narsa sozlanmagan.\n"
            "Quyidagi tugmalardan birini bosing:"
        )
    return (
        "⚙️ <b>Sozlamalar</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"💰 Boshlang'ich balans: <b>{s.get('starting_balance') or '—'}$</b>\n"
        f"📊 Kunlik foiz: <b>{int((s.get('daily_profit_rate') or 0.20) * 100)}%</b>\n"
        f"➕ Qo'shimcha maqsad: <b>{s.get('extra_target') or 0}$</b>\n"
        f"💸 Yechish summasi: <b>{s.get('withdrawal_amount') or 0}$</b>\n"
        f"📅 Yechish davri: <b>har {s.get('withdrawal_every') or '—'} kunda</b>\n"
        f"🗓 Kun soni: <b>{s.get('total_days') or '—'} kun</b>\n"
        f"📆 Boshlanish: <b>{s.get('start_date') or '—'}</b>\n"
        f"🌍 Timezone: <b>{s.get('timezone') or 'Asia/Tashkent'}</b>\n"
        f"⏰ Eslatma: <b>{s.get('reminder_time') or '08:00'}</b>\n"
    )


# ===== BALANCE =====
@router.callback_query(F.data == "set_balance")
async def ask_balance(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.balance)
    await call.message.edit_text(
        "💰 Boshlang'ich balans kiriting (USD):\n<i>Masalan: 50</i>",
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
            _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri raqam. Qayta kiriting:", reply_markup=cancel_kb(), parse_mode="HTML"
        )


# ===== RATE =====
@router.callback_query(F.data == "set_rate")
async def ask_rate(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.rate)
    await call.message.edit_text(
        "📊 Kunlik foiz kiriting (%):\n<i>Masalan: 20</i>",
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
            _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ 1 dan 100 gacha raqam kiriting:", reply_markup=cancel_kb(), parse_mode="HTML"
        )


# ===== EXTRA TARGET =====
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
            _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri raqam. Qayta kiriting:", reply_markup=cancel_kb(), parse_mode="HTML"
        )


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
            _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri raqam. Qayta kiriting:", reply_markup=cancel_kb(), parse_mode="HTML"
        )


# ===== WITHDRAWAL EVERY =====
@router.callback_query(F.data == "set_wevery")
async def ask_wevery(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.wevery)
    await call.message.edit_text(
        "📅 Har necha kunda yechish?\n<i>Masalan: 7 (har 7 kunda)</i>",
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
            _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Musbat butun son kiriting:", reply_markup=cancel_kb(), parse_mode="HTML"
        )


# ===== DAYS =====
@router.callback_query(F.data == "set_days")
async def ask_days(call: CallbackQuery, state: FSMContext):
    await state.set_state(SettingsForm.days)
    await call.message.edit_text(
        "🗓 Strategiya kun sonini kiriting:\n<i>Masalan: 7</i>",
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
            _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Musbat butun son kiriting:", reply_markup=cancel_kb(), parse_mode="HTML"
        )


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
            _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Format noto'g'ri. Qayta kiriting:\n<i>Masalan: 01.11.2025</i>",
            reply_markup=cancel_kb(), parse_mode="HTML"
        )


# ===== TIMEZONE =====
@router.callback_query(F.data == "set_timezone")
async def ask_timezone(call: CallbackQuery, state: FSMContext):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=tz, callback_data=f"tz_{tz}")] for tz in TIMEZONES
    ] + [[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="settings_back")]])
    await call.message.edit_text(
        "🌍 Timezoneni tanlang:", reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("tz_"))
async def save_timezone(call: CallbackQuery, db_user_id: int):
    tz = call.data[3:]
    await upsert_setting(db_user_id, "timezone", tz)
    s = await get_settings(db_user_id)
    await call.message.edit_text(
        _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
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
            _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
        )
    except ValueError:
        await message.answer(
            "⚠️ Format noto'g'ri. Qayta kiriting:\n<i>Masalan: 08:00</i>",
            reply_markup=cancel_kb(), parse_mode="HTML"
        )


@router.callback_query(F.data == "settings_back")
async def settings_back(call: CallbackQuery, state: FSMContext, db_user_id: int):
    await state.clear()
    s = await get_settings(db_user_id)
    await call.message.edit_text(
        _settings_text(s), reply_markup=settings_inline(), parse_mode="HTML"
    )
    await call.answer()
