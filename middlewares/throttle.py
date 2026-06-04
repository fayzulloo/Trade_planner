"""
Throttling middleware — spam himoyasi.
Bir foydalanuvchi qisqa vaqt ichida ko'p xabar yubora olmaydi.
"""

import logging
from typing import Any, Callable, Awaitable
from datetime import datetime, timedelta

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

logger = logging.getLogger(__name__)

# Throttle sozlamalari
THROTTLE_RATE = 0.7  # soniya (minimum xabarlar orasidagi vaqt)

# Xotira: {telegram_id: last_message_time}
_last_message: dict[int, datetime] = {}


class ThrottleMiddleware(BaseMiddleware):
    """
    Har bir foydalanuvchi uchun xabar chastotasini cheklaydi.
    THROTTLE_RATE soniyadan tez xabar kelsa — e'tiborsiz qoldiriladi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """
        Throttle tekshiruvi.
        """
        if not isinstance(event, Message):
            # Callback query lar cheklanmaydi
            return await handler(event, data)

        tg_user = event.from_user
        if not tg_user:
            return await handler(event, data)

        now = datetime.now()
        last = _last_message.get(tg_user.id)

        if last and (now - last) < timedelta(seconds=THROTTLE_RATE):
            # Juda tez — e'tiborsiz qoldirish
            logger.debug(f"Throttle [tg_id={tg_user.id}]: xabar tashlab ketildi")
            return

        _last_message[tg_user.id] = now
        return await handler(event, data)
