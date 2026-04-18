from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Awaitable, Any
from database.queries import get_or_create_user, is_settings_complete
from utils.logger import logger


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            try:
                user_id = await get_or_create_user(user.id, user.username or "")
                data["db_user_id"] = user_id
                data["settings_complete"] = await is_settings_complete(user_id)
            except Exception as e:
                logger.error(f"Auth middleware xatosi: {e}")
                data["db_user_id"] = None
                data["settings_complete"] = False

        return await handler(event, data)
