from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from typing import Callable, Awaitable, Any
from collections import defaultdict
import time
from utils.logger import logger

THROTTLE_RATE = 1.0  # soniyada bir xabar


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self):
        self.user_timestamps = defaultdict(float)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
            now = time.time()
            if now - self.user_timestamps[uid] < THROTTLE_RATE:
                logger.warning(f"Throttle: {uid}")
                await event.answer("⏳ Iltimos, biroz kuting...")
                return
            self.user_timestamps[uid] = now

        return await handler(event, data)
