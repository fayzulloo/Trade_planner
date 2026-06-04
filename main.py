"""
Trade Planner Bot — asosiy entry point.
Railway worker service sifatida ishlaydi.
Webhook yoki polling rejimida ishlaydi.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import BOT_TOKEN, BOT_WEBHOOK_URL, WEBAPP_URL, PORT
from database.connection import create_pool, close_pool
from database.models import init_db
from middlewares import AuthMiddleware, ThrottleMiddleware
from handlers import start, plan, trade, settings, stats
from scheduler import setup_scheduler
from utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"


async def on_startup(bot: Bot) -> None:
    """Webhook ni Telegram ga ro'yxatdan o'tkazadi."""
    webhook_url = f"{BOT_WEBHOOK_URL}{WEBHOOK_PATH}"
    await bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    logger.info(f"Webhook o'rnatildi: {webhook_url}")


async def on_shutdown(bot: Bot) -> None:
    """Webhook ni o'chiradi."""
    await bot.delete_webhook()
    await close_pool()
    await bot.session.close()
    logger.info("Bot to'xtatildi.")


async def start_polling(bot: Bot, dp: Dispatcher) -> None:
    """Polling rejimida ishga tushiradi."""
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


async def main() -> None:
    """
    Botni ishga tushiradi.
    BOT_WEBHOOK_URL mavjud bo'lsa — webhook, aks holda polling.
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

    # 6. Webhook yoki Polling
    if BOT_WEBHOOK_URL:
        logger.info("Webhook rejimida ishga tushmoqda...")

        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
        await site.start()

        logger.info(f"Webhook server port {PORT} da ishlamoqda.")

        # Server doim ishlash uchun
        await asyncio.Event().wait()
    else:
        await start_polling(bot, dp)


if __name__ == "__main__":
    asyncio.run(main())
