from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from handlers.keyboards import main_keyboard
from utils.logger import logger

router = Router()


@router.message(CommandStart())
async def start(message: Message, db_user_id: int, settings_complete: bool):
    logger.info(f"/start: {message.from_user.id}")
    name = message.from_user.first_name or "Trader"

    if not settings_complete:
        await message.answer(
            f"Salom, {name}! 👋\n\n"
            "Trade Planner botiga xush kelibsiz.\n\n"
            "⚠️ Botdan foydalanish uchun avval strategiyangizni sozlang.\n\n"
            "👇 Quyidagi tugmani bosing:",
            reply_markup=main_keyboard()
        )
        await message.answer(
            "⚙️ Sozlamalarni to'ldirish uchun <b>Sozlamalar</b> tugmasini bosing.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"Salom, {name}! 👋\n\n"
            "Trade Planner tayyor. Bugungi rejangizni ko'rish uchun "
            "<b>📊 Bugungi reja</b> tugmasini bosing.",
            reply_markup=main_keyboard(),
            parse_mode="HTML"
        )
