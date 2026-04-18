import asyncpg
from config import DATABASE_URL
from utils.logger import logger

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool ishga tushmagan!")
    return _pool


async def init_pool():
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
            statement_cache_size=0
        )
        logger.info("PostgreSQL connection pool yaratildi.")
    except Exception as e:
        logger.critical(f"PostgreSQL ulanishda xato: {e}")
        raise


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        logger.info("PostgreSQL connection pool yopildi.")
