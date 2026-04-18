import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database.connection import init_pool, close_pool
from database.models import init_db, migrate_db
from handlers import start, plan, trade, settings, stats
from middlewares.auth import AuthMiddleware
from middlewares.throttle import ThrottleMiddleware
from scheduler.scheduler import setup_scheduler
from utils.logger import logger


async def main():
    logger.info("Bot ishga tushmoqda...")

    # PostgreSQL pool
    await init_pool()

    # Jadvallar va migration
    await init_db()
    await migrate_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares
    dp.message.middleware(ThrottleMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Routers
    dp.include_router(start.router)
    dp.include_router(plan.router)
    dp.include_router(trade.router)
    dp.include_router(settings.router)
    dp.include_router(stats.router)

    # Scheduler
    setup_scheduler(bot)

    logger.info("Bot muvaffaqiyatli ishga tushdi.")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    except Exception as e:
        logger.critical(f"Bot to'xtadi: {e}")
    finally:
        await close_pool()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    asyncio.run(main())
