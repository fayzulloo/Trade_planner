"""
Trade Planner Bot — asosiy entry point.
Railway worker service sifatida ishlaydi.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database.connection import create_pool, close_pool
from database.models import init_db
from middlewares import AuthMiddleware, ThrottleMiddleware
from handlers import start, plan, trade, settings, stats
from scheduler import setup_scheduler
from utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Botni ishga tushiradi:
    1. Database pool va jadvallar
    2. Bot va Dispatcher
    3. Middleware lar
    4. Handler lar
    5. Scheduler
    6. Polling
    """
    # 1. Database
    await create_pool()
    await init_db()
    logger.info("Database tayyor.")

    # 2. Bot va Dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # 3. Middleware lar
    # ⚠️ Diqqat: Avval throttle, keyin auth — tartib muhim
    # Throttle spam xabarlarni auth ga yetmasdan to'xtatadi
    dp.message.middleware(ThrottleMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # 4. Handler routerlar
    dp.include_router(start.router)
    dp.include_router(plan.router)
    dp.include_router(trade.router)
    dp.include_router(settings.router)
    dp.include_router(stats.router)

    # 5. Scheduler
    await setup_scheduler(bot)

    # 6. Polling
    logger.info("Bot polling boshlanmoqda...")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
    finally:
        await close_pool()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    asyncio.run(main())
