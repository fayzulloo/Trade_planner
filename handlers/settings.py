"""
Sozlamalar handlerlari.
Har bir sozlama uchun FSM oqimi.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.queries import get_settings, save_settings
from handlers.keyboards import (
    settings_kb, cancel_settings_kb,
    timezone_kb, rest_days_kb,
    evening_reminder_kb, broker_kb,
    main_menu_kb,
)
from utils.calculator import parse_time_str, parse_start_date

logger = logging.getLogger(__name__)
router = Router()


class SettingsForm(StatesGroup):
    """Sozlama qiymatini kutish."""
    waiting = State()


# Qaysi sozlama tahrirlanyapti
SETTING_KEY = "setting_key"

# Sozlama tavsiflari (foydalanuvchiga ko'rsatiladigan)
SETTING_LABELS = {
    "set_balance":          ("starting_balance",     "💰 Boshlang'ich balansni kiriting ($):"),
    "set_rate":             ("daily_profit_rate",    "📊 Kunlik foiz kiriting (masalan: 10 yoki 0.10):"),
    "set_extra":            ("extra_target",         "➕ Qo'shimcha kunlik maqsad kiriting ($):"),
    "set_withdrawal":       ("withdrawal_amount",    "💸 Yechish summasi kiriting ($):"),
    "set_wevery":           ("withdrawal_every",     "📅 Har necha kunda yechish? (masalan: 7):"),
    "set_days":             ("total_days",           "🗓 Strategiya davri (kun soni, masalan: 20):"),
    "set_startdate":        ("start_date",           "📆 Boshlanish sanasi kiriting (DD.MM.YYYY):"),
    "set_reminder":         ("reminder_time",        "⏰ Ertalabki eslatma vaqti (HH:MM, masalan: 08:00):"),
    "set_auto_complete":    ("auto_complete_time",   "🔄 Avtomatik yakunlash vaqti (HH:MM, masalan: 23:30):"),
}


async def _show_settings(target, user_id: int) -> None:
    """
    Sozlamalar menyusini ko'rsatadi.
    target — Message yoki CallbackQuery.message
    """
    settings = await get_settings(user_id)
    text = "⚙️ <b>Sozlamalar</b>\n\nO'zgartirmoqchi bo'lgan sozlamani tanlang:"
    kb = settings_kb(dict(settings) if settings else {})
    try:
        await target.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "⚙️ Sozlamalar")
async def open_settings_message(message: Message, user_id: int, **kwargs) -> None:
    """Sozlamalar menyusini ochish (Reply keyboard orqali)."""
    try:
        settings = await get_settings(user_id)
        text = "⚙️ <b>Sozlamalar</b>\n\nO'zgartirmoqchi bo'lgan sozlamani tanlang:"
        await message.answer(
            text,
            reply_markup=settings_kb(dict(settings) if settings else {}),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"open_settings_message xato [user_id={user_id}]: {e}")


@router.callback_query(F.data == "settings_open")
async def open_settings_callback(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Sozlamalar menyusini ochish (callback orqali)."""
    try:
        await _show_settings(callback.message, user_id)
    except Exception as e:
        logger.error(f"open_settings_callback xato [user_id={user_id}]: {e}")
    finally:
        await callback.answer()


# ─────────────────────────────────────────────
# ODDIY MATN KIRITISH SOZLAMALARI
# ─────────────────────────────────────────────

@router.callback_query(F.data.in_(SETTING_LABELS.keys()))
async def setting_ask_value(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """Sozlama qiymati so'rash."""
    cb = callback.data
    _, prompt = SETTING_LABELS[cb]
    await state.set_state(SettingsForm.waiting)
    await state.update_data(**{SETTING_KEY: cb})
    await callback.message.edit_text(
        prompt,
        reply_markup=cancel_settings_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SettingsForm.waiting)
async def setting_save_value(message: Message, state: FSMContext, user_id: int, **kwargs) -> None:
    """
    Sozlama qiymatini saqlash.
    Har bir sozlama uchun validatsiya qilinadi.
    Maxsus keylar (evening_reminder, broker) ham shu yerda qayta ishlanadi.
    """
    data = await state.get_data()
    cb = data.get(SETTING_KEY)
    if not cb:
        await state.clear()
        return

    raw = message.text.strip()

    # Maxsus holat: kechki eslatma
    if cb == "set_evening_reminder_custom":
        if not parse_time_str(raw):
            await message.answer(
                "⚠️ Noto'g'ri format. HH:MM ko'rinishida kiriting:",
                reply_markup=cancel_settings_kb(),
            )
            return
        await state.clear()
        try:
            await save_settings(user_id, evening_reminder_time=raw)
            settings = await get_settings(user_id)
            await message.answer(
                "✅ Saqlandi!\n\n⚙️ <b>Sozlamalar</b>",
                reply_markup=settings_kb(dict(settings) if settings else {}),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"evening_reminder save xato [user_id={user_id}]: {e}")
            await message.answer("⚠️ Saqlashda xato yuz berdi.")
        return

    # Maxsus holat: broker nomi
    if cb == "set_broker_custom":
        await state.clear()
        try:
            await save_settings(user_id, broker_name=raw)
            settings = await get_settings(user_id)
            await message.answer(
                "✅ Saqlandi!\n\n⚙️ <b>Sozlamalar</b>",
                reply_markup=settings_kb(dict(settings) if settings else {}),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"broker save xato [user_id={user_id}]: {e}")
            await message.answer("⚠️ Saqlashda xato yuz berdi.")
        return

    # Oddiy sozlamalar
    if cb not in SETTING_LABELS:
        await state.clear()
        return

    db_key, _ = SETTING_LABELS[cb]

    try:
        value = _parse_setting_value(cb, raw)
    except ValueError as e:
        await message.answer(f"⚠️ {e}\nQaytadan kiriting:", reply_markup=cancel_settings_kb())
        return

    await state.clear()

    try:
        await save_settings(user_id, **{db_key: value})

        # Sozlamalar to'liq bo'lsa is_active = TRUE
        await _check_and_activate(user_id)

        settings = await get_settings(user_id)
        await message.answer(
            "✅ Saqlandi!\n\n⚙️ <b>Sozlamalar</b>",
            reply_markup=settings_kb(dict(settings) if settings else {}),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"setting_save_value xato [user_id={user_id}]: {e}")
        await message.answer("⚠️ Saqlashda xato yuz berdi.")


def _parse_setting_value(cb: str, raw: str):
    """
    Sozlama qiymatini to'g'ri tipga o'giradi.
    ValueError chiqaradi — noto'g'ri format bo'lsa.
    """
    if cb == "set_balance":
        v = float(raw.replace(",", ".").replace("$", ""))
        if v <= 0:
            raise ValueError("Balans musbat bo'lishi kerak.")
        return v

    elif cb == "set_rate":
        v = float(raw.replace(",", ".").replace("%", ""))
        # 10 → 0.10 avtomatik konversiya
        if v > 1:
            v = v / 100
        if not (0 < v <= 1):
            raise ValueError("Foiz 0 dan katta, 100 dan kichik bo'lishi kerak.")
        return v

    elif cb in ("set_extra", "set_withdrawal"):
        v = float(raw.replace(",", ".").replace("$", ""))
        if v < 0:
            raise ValueError("Qiymat manfiy bo'lishi mumkin emas.")
        return v

    elif cb in ("set_wevery", "set_days"):
        v = int(raw)
        if v <= 0:
            raise ValueError("Qiymat musbat son bo'lishi kerak.")
        return v

    elif cb == "set_startdate":
        d = parse_start_date(raw)
        if not d:
            raise ValueError("Noto'g'ri format. DD.MM.YYYY ko'rinishida kiriting.")
        return raw  # DB da TEXT saqlanadi

    elif cb in ("set_reminder", "set_auto_complete"):
        if not parse_time_str(raw):
            raise ValueError("Noto'g'ri format. HH:MM ko'rinishida kiriting.")
        return raw

    return raw


async def _check_and_activate(user_id: int) -> None:
    """
    Barcha majburiy sozlamalar to'liq bo'lsa is_active = TRUE qiladi.
    Majburiy: starting_balance, start_date, total_days.
    """
    settings = await get_settings(user_id)
    if not settings:
        return
    if (
        settings.get("starting_balance") and
        settings.get("start_date") and
        settings.get("total_days")
    ):
        await save_settings(user_id, is_active=True)


# ─────────────────────────────────────────────
# TIMEZONE
# ─────────────────────────────────────────────

@router.callback_query(F.data == "set_timezone")
async def ask_timezone(callback: CallbackQuery, **kwargs) -> None:
    """Timezone tanlash menyusi."""
    await callback.message.edit_text(
        "🌍 Timezone tanlang:",
        reply_markup=timezone_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tz_"))
async def save_timezone(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Timezone saqlash."""
    tz = callback.data[3:]
    try:
        await save_settings(user_id, timezone=tz)
        await _show_settings(callback.message, user_id)
    except Exception as e:
        logger.error(f"save_timezone xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


# ─────────────────────────────────────────────
# KECHKI ESLATMA
# ─────────────────────────────────────────────

@router.callback_query(F.data == "set_evening_reminder")
async def ask_evening_reminder(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """Kechki eslatma vaqti so'rash."""
    await state.set_state(SettingsForm.waiting)
    await state.update_data(**{SETTING_KEY: "set_evening_reminder_custom"})
    await callback.message.edit_text(
        "🌙 Kechki eslatma vaqti kiriting (HH:MM):",
        reply_markup=evening_reminder_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "clear_evening_reminder")
async def clear_evening_reminder(callback: CallbackQuery, user_id: int, state: FSMContext, **kwargs) -> None:
    """Kechki eslatmani o'chirish."""
    await state.clear()
    try:
        await save_settings(user_id, evening_reminder_time=None)
        await _show_settings(callback.message, user_id)
    except Exception as e:
        logger.error(f"clear_evening_reminder xato [user_id={user_id}]: {e}")
    finally:
        await callback.answer()


# ─────────────────────────────────────────────
# BROKER
# ─────────────────────────────────────────────

@router.callback_query(F.data == "set_broker")
async def ask_broker(callback: CallbackQuery, state: FSMContext, **kwargs) -> None:
    """Broker nomi so'rash."""
    await state.set_state(SettingsForm.waiting)
    await state.update_data(**{SETTING_KEY: "set_broker_custom"})
    await callback.message.edit_text(
        "🏦 Broker nomini kiriting:",
        reply_markup=broker_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "clear_broker")
async def clear_broker(callback: CallbackQuery, user_id: int, state: FSMContext, **kwargs) -> None:
    """Broker nomini o'chirish."""
    await state.clear()
    try:
        await save_settings(user_id, broker_name=None)
        await _show_settings(callback.message, user_id)
    except Exception as e:
        logger.error(f"clear_broker xato [user_id={user_id}]: {e}")
    finally:
        await callback.answer()


# ─────────────────────────────────────────────
# DAM OLISH KUNLARI
# ─────────────────────────────────────────────

@router.callback_query(F.data == "set_rest_days")
async def ask_rest_days(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Dam olish kunlari menyusi."""
    settings = await get_settings(user_id)
    current = settings.get("rest_days", "6,7") if settings else "6,7"
    await callback.message.edit_text(
        "🗓 Dam olish kunlarini tanlang:",
        reply_markup=rest_days_kb(current or ""),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rd_toggle_"))
async def toggle_rest_day(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Dam olish kunini yoqish/o'chirish."""
    code = int(callback.data.split("_")[-1])
    settings = await get_settings(user_id)
    current_str = settings.get("rest_days", "") if settings else ""

    selected = set()
    if current_str:
        selected = {int(x.strip()) for x in current_str.split(",") if x.strip().isdigit()}

    if code in selected:
        selected.discard(code)
    else:
        selected.add(code)

    new_val = ",".join(str(d) for d in sorted(selected))

    # Vaqtinchalik state da saqlaymiz (hali DB ga emas)
    # Callback message dagi tugmalarni yangilaymiz
    await callback.message.edit_reply_markup(
        reply_markup=rest_days_kb(new_val)
    )

    # ⚠️ Diqqat: toggle bosimda vaqtinchalik qiymat
    # rd_save bosilganda saqlash uchun callbackda current ni o'qiymiz
    # Shu sababli hozircha DB ga yozamiz (har toggle da)
    await save_settings(user_id, rest_days=new_val)
    await callback.answer()


@router.callback_query(F.data == "rd_save")
async def save_rest_days(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Dam olish kunlarini saqlash."""
    try:
        await _show_settings(callback.message, user_id)
    except Exception as e:
        logger.error(f"save_rest_days xato [user_id={user_id}]: {e}")
    finally:
        await callback.answer("✅ Saqlandi!")


# ─────────────────────────────────────────────
# SAQLASH VA YOPISH
# ─────────────────────────────────────────────

@router.callback_query(F.data == "settings_save")
async def settings_save(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """Sozlamalarni saqlash va yopish."""
    try:
        await _check_and_activate(user_id)
        settings = await get_settings(user_id)
        is_active = settings.get("is_active") if settings else False

        if is_active:
            await callback.message.edit_text(
                "✅ <b>Sozlamalar saqlandi!</b>\n\n"
                "Endi 📊 Bugungi reja dan boshlashingiz mumkin.",
                parse_mode="HTML",
            )
        else:
            await callback.message.edit_text(
                "⚠️ <b>Sozlamalar to'liq emas!</b>\n\n"
                "Kamida quyidagilar kerak:\n"
                "• 💰 Boshlang'ich balans\n"
                "• 📆 Boshlanish sanasi\n"
                "• 🗓 Kun soni",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.error(f"settings_save xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()
