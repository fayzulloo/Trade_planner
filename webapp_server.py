"""
WebApp server — Railway web service sifatida ishlaydi.
Bot bilan bir xil PostgreSQL ga ulanadi.
"""

import logging
import uvicorn
from contextlib import asynccontextmanager

from database.connection import create_pool, close_pool
from database.models import init_db
from utils.logger import setup_logger
from config import PORT

setup_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Server ishga tushganda va to'xtaganda."""
    logger.info("WebApp server ishga tushmoqda...")
    await create_pool()
    await init_db()
    logger.info("WebApp server tayyor.")
    yield
    await close_pool()
    logger.info("WebApp server to'xtatildi.")


# webapp/app.py dagi app ni to'g'ridan import qilamiz
# lifespan ni alohida o'rnatamiz
from webapp.app import app  # noqa: E402
app.router.lifespan_context = lifespan


if __name__ == "__main__":
    uvicorn.run(
        "webapp_server:app",
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
    )
