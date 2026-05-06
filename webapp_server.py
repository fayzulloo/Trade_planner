"""
WebApp server — Railway web service sifatida ishlaydi.
Bot bilan bir xil PostgreSQL ga ulanadi.
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI

from database.connection import create_pool, close_pool
from database.models import init_db
from utils.logger import setup_logger
from config import PORT

setup_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server ishga tushganda va to'xtaganda."""
    logger.info("WebApp server ishga tushmoqda...")
    await create_pool()
    await init_db()
    logger.info("WebApp server tayyor.")
    yield
    await close_pool()
    logger.info("WebApp server to'xtatildi.")


# ⚠️ Diqqat: app ni import qilishdan OLDIN lifespan tayyor bo'lishi kerak
# webapp/app.py da app = FastAPI(lifespan=lifespan) emas,
# shu yerda lifespan ni alohida FastAPI ga bog'laymiz
app = FastAPI(title="Trade Planner WebApp", lifespan=lifespan)

# webapp routes ni app ga qo'shamiz
from webapp.app import router as webapp_router  # noqa: E402
app.include_router(webapp_router)


if __name__ == "__main__":
    uvicorn.run(
        "webapp_server:app",
        host="0.0.0.0",
        port=PORT,
        log_level="warning",
    )
