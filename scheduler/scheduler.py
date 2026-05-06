"""
APScheduler sozlash va job registratsiyasi.
Har bir foydalanuvchining timezone va vaqtiga qarab dinamik job qo'shadi.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from database.queries import get_all_active_users
from scheduler.jobs import (
    job_create_daily_journals,
    job_morning_reminder,
    job_evening_reminder,
    job_auto_complete,
)
from utils.calculator import parse_time_str

logger = logging.getLogger(__name__)

# Global scheduler obyekti
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """
    Mavjud scheduler ni qaytaradi.
    """
    if _scheduler is None:
        raise RuntimeError("Scheduler yaratilmagan. Avval setup_scheduler() chaqiring.")
    return _scheduler


async def setup_scheduler(bot) -> AsyncIOScheduler:
    """
    Scheduler ni yaratadi va barcha joblarni ro'yxatdan o'tkazadi.
    main.py da ishga tushganda bir marta chaqiriladi.

    Arxitektura:
    - Har bir job BARCHA userlarni o'zi ichida aylanadi
    - Har user uchun alohida job EMAS — umumiy joblar ishlaydi
    - Job ichida har user o'z timezone va vaqtini tekshiradi

    Joblar (barchasi UTC da har daqiqa ishlaydi, ichida vaqt tekshiriladi):
    1. create_daily_journals — 00:01 UTC
    2. morning_reminder      — har daqiqa (ichida reminder_time tekshiriladi)
    3. evening_reminder      — har daqiqa (ichida evening_reminder_time tekshiriladi)
    4. auto_complete         — har daqiqa (ichida auto_complete_time tekshiriladi)
    """
    global _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # 1. Kunlik journal yaratish — 00:01 UTC
    _scheduler.add_job(
        _wrap(job_create_daily_journals, bot),
        CronTrigger(hour=0, minute=1, timezone="UTC"),
        id="create_daily_journals",
        replace_existing=True,
    )

    # 2. Ertalabki eslatma — har daqiqa tekshiriladi
    _scheduler.add_job(
        _wrap(job_morning_reminder, bot),
        CronTrigger(minute="*", timezone="UTC"),
        id="morning_reminder",
        replace_existing=True,
    )

    # 3. Kechki eslatma — har daqiqa tekshiriladi
    _scheduler.add_job(
        _wrap(job_evening_reminder, bot),
        CronTrigger(minute="*", timezone="UTC"),
        id="evening_reminder",
        replace_existing=True,
    )

    # 4. Avtomatik yakunlash — har daqiqa tekshiriladi
    _scheduler.add_job(
        _wrap(job_auto_complete, bot),
        CronTrigger(minute="*", timezone="UTC"),
        id="auto_complete",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler ishga tushdi. Jami 4 ta job.")
    return _scheduler


def remove_user_jobs(user_id: int) -> None:
    """
    Bu arxitekturada alohida user joblar yo'q.
    Eski kod bilan moslik uchun saqlanadi.
    """
    pass


def refresh_user_jobs(bot, user_id: int, settings: dict) -> None:
    """
    Bu arxitekturada alohida user joblar yo'q.
    Eski kod bilan moslik uchun saqlanadi.
    """
    pass


def _wrap(job_func, bot):
    """
    Job funksiyasini bot bilan o'rab qaytaradi.
    APScheduler callable sifatida ishlatadi.
    """
    async def wrapper():
        await job_func(bot)
    return wrapper
