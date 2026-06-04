"""
/start komandasi va rejim tanlash handlerlari.
"""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.queries import (
    get_settings, save_settings,
    finish_strategy,
)
from handlers.keyboards import main_menu_kb, mode_select_kb
from utils.calculator import get_current_date, format_date

logger = logging.getLogger(__name__)
router = Router()


class JournalSetupForm(StatesGroup):
    """Jurnal rejimi uchun boshlang'ich balans so'rash."""
    waiting_balance = State()


@router.message(CommandStart())
async def cmd_start(message: Message, user_id: int, **kwargs) -> None:
    """
    /start komandasi.
    Agar sozlamalar yo'q yoki is_active=FALSE bo'lsa — rejim tanlash.
    """
    try:
        settings = await get_settings(user_id)
        name = message.from_user.first_name or "Do'st"

        if not settings or not settings["is_active"]:
            await message.answer(
                f"👋 Salom, {name}!\n\n"
                f"📊 <b>Trade Planner</b> ga xush kelibsiz!\n\n"
                f"Qanday davom etmoqchisiz?",
                reply_markup=mode_select_kb(),
                parse_mode="HTML",
            )
        else:
            mode = settings.get("mode", "strategy")
            if mode == "journal":
                await message.answer(
                    f"👋 Xush kelibsiz, {name}!\n\n"
                    f"📝 Jurnal rejimida ishlayapsiz.",
                    reply_markup=main_menu_kb(),
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    f"👋 Xush kelibsiz, {name}!\n\n"
                    f"Bugungi rejangizni ko'rish uchun 📊 <b>Bugungi reja</b> tugmasini bosing.",
                    reply_markup=main_menu_kb(),
                    parse_mode="HTML",
                )
    except Exception as e:
        logger.error(f"cmd_start xato [user_id={user_id}]: {e}")
        await message.answer("⚠️ Xato yuz berdi.")


@router.callback_query(F.data == "select_mode_strategy")
async def select_mode_strategy(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """
    Strategiya rejimi tanlandi.
    Sozlamalarga yo'naltiradi.
    """
    try:
        await save_settings(user_id, mode="strategy")
        await callback.message.edit_text(
            "📊 <b>Strategiya rejimi</b> tanlandi.\n\n"
            "⚙️ Sozlamalar ga o'tib strategiyangizni sozlang.",
            parse_mode="HTML",
        )
        await callback.message.answer(
            "Boshlash uchun sozlamalarni kiriting:",
            reply_markup=main_menu_kb(),
        )
    except Exception as e:
        logger.error(f"select_mode_strategy xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


@router.callback_query(F.data == "select_mode_journal")
async def select_mode_journal(callback: CallbackQuery, user_id: int, state: FSMContext, **kwargs) -> None:
    """
    Jurnal rejimi tanlandi.
    Avval boshlang'ich balans so'raladi, keyin faollashtiriladi.
    """
    try:
        # Faqat rejimni saqlaymiz — is_active hali FALSE
        await save_settings(user_id, mode="journal", is_active=False)
        await state.set_state(JournalSetupForm.waiting_balance)
        await callback.message.edit_text(
            "📝 <b>Jurnal rejimi</b>\n\n"
            "💰 Boshlang'ich balansingizni kiriting ($):\n"
            "<i>Masalan: 1000 yoki 1500.50</i>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"select_mode_journal xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()


@router.message(JournalSetupForm.waiting_balance)
async def journal_set_balance(message: Message, user_id: int, state: FSMContext, **kwargs) -> None:
    """
    Jurnal rejimi uchun boshlang'ich balans kiritildi.
    Saqlaydi va faollashtiradi.
    """
    try:
        balance = float(message.text.replace(",", ".").replace("+", ""))
        if balance <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri qiymat. Musbat son kiriting (masalan: 1000):"
        )
        return

    await state.clear()
    await save_settings(user_id, starting_balance=balance, is_active=True)
    await message.answer(
        f"✅ <b>Jurnal rejimi faollashtirildi!</b>\n\n"
        f"💰 Boshlang'ich balans: <b>${balance:,.2f}</b>\n\n"
        f"Savdo kiritishni boshlashingiz mumkin.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "new_strategy")
async def new_strategy(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """
    Yangi strategiya — rejim tanlash ekraniga qaytadi.
    finish_strategy allaqachon _handle_strategy_finished da chaqirilgan.
    """
    try:
        await callback.message.edit_text(
            "🔄 Qanday davom etmoqchisiz?",
            reply_markup=mode_select_kb(),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"new_strategy xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()
