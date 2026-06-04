"""
PostgreSQL ulanish pool boshqaruvi.
asyncpg orqali asinxron ulanish.
"""

import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# Global pool obyekti
_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    """
    PostgreSQL connection pool yaratadi.
    Ilova ishga tushganda bir marta chaqiriladi.
    """
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("PostgreSQL pool muvaffaqiyatli yaratildi.")
        return _pool
    except Exception as e:
        logger.error(f"Pool yaratishda xato: {e}")
        raise


async def get_pool() -> asyncpg.Pool:
    """
    Mavjud pool ni qaytaradi.
    Pool yaratilmagan bo'lsa xato chiqaradi.
    """
    if _pool is None:
        raise RuntimeError("Pool yaratilmagan. Avval create_pool() chaqiring.")
    return _pool


async def close_pool() -> None:
    """
    Pool ni yopadi.
    Ilova to'xtaganda chaqiriladi.
    """
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool yopildi.")
