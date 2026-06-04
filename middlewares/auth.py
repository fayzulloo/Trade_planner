"""
Autentifikatsiya middleware.
Har bir xabarda foydalanuvchini tekshiradi va ro'yxatdan o'tkazadi.
"""

import logging
from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database.queries import get_or_create_user

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    Har bir update da foydalanuvchini bazadan topadi yoki yaratadi.
    user va settings ni data ga qo'shadi — handlerlarda ishlatish uchun.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Middleware asosiy logikasi.
        """
        # Telegram user obyektini olish
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        if tg_user:
            try:
                user = await get_or_create_user(
                    telegram_id=tg_user.id,
                    username=tg_user.username,
                )
                # Handlerlarga uzatish
                data["db_user"] = user
                data["user_id"] = user["id"]
            except Exception as e:
                logger.error(f"AuthMiddleware xato [tg_id={tg_user.id}]: {e}")
                # Xato bo'lsa ham handlega o'tadi, lekin db_user bo'lmaydi
                data["db_user"] = None
                data["user_id"] = None

        return await handler(event, data)
