"""
/start komandasi va yangi strategiya boshlash handlerlari.
"""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from database.queries import get_settings, finish_strategy
from handlers.keyboards import main_menu_kb, strategy_finished_kb

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user_id: int, **kwargs) -> None:
    """
    /start komandasi.
    Foydalanuvchini kutib oladi va asosiy menyuni ko'rsatadi.
    AuthMiddleware user_id ni data ga qo'shgan bo'ladi.
    """
    try:
        settings = await get_settings(user_id)
        name = message.from_user.first_name or "Do'st"

        if not settings or not settings["is_active"]:
            await message.answer(
                f"👋 Salom, {name}!\n\n"
                "📊 <b>Trade Planner</b> ga xush kelibsiz!\n\n"
                "Boshlash uchun ⚙️ <b>Sozlamalar</b> ga o'ting va "
                "strategiyangizni sozlang.",
                reply_markup=main_menu_kb(),
                parse_mode="HTML",
            )
        else:
            await message.answer(
                f"👋 Xush kelibsiz, {name}!\n\n"
                "Bugungi rejangizni ko'rish uchun 📊 <b>Bugungi reja</b> tugmasini bosing.",
                reply_markup=main_menu_kb(),
                parse_mode="HTML",
            )
    except Exception as e:
        logger.error(f"cmd_start xato [user_id={user_id}]: {e}")
        await message.answer("⚠️ Xato yuz berdi. Qaytadan urinib ko'ring.")


@router.callback_query(F.data == "new_strategy")
async def new_strategy(callback: CallbackQuery, user_id: int, **kwargs) -> None:
    """
    Yangi strategiya boshlash.
    Eski sozlamalarni tozalab, sozlamalar menyusiga yo'naltiradi.
    """
    try:
        await finish_strategy(user_id)
        await callback.message.edit_text(
            "🔄 <b>Yangi strategiya</b>\n\n"
            "Yangi strategiya uchun sozlamalarni kiriting.\n"
            "⚙️ Sozlamalar menyusiga o'ting.",
            parse_mode="HTML",
        )
        await callback.message.answer(
            "⚙️ Sozlamalarni yangilang:",
            reply_markup=main_menu_kb(),
        )
    except Exception as e:
        logger.error(f"new_strategy xato [user_id={user_id}]: {e}")
        await callback.answer("⚠️ Xato yuz berdi.", show_alert=True)
    finally:
        await callback.answer()
