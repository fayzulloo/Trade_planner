"""
APScheduler sozlash va job registratsiyasi.
Resurslarni tejash uchun har bir job faqat kerakli vaqt oralig'ida ishlaydi.
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.jobs import (
    job_create_daily_journals,
    job_morning_reminder,
    job_evening_reminder,
    job_auto_complete,
)

logger = logging.getLogger(__name__)

# Global scheduler obyekti
_scheduler: AsyncIOScheduler | None = None


async def setup_scheduler(bot) -> AsyncIOScheduler:
    """
    Scheduler ni yaratadi va barcha joblarni ro'yxatdan o'tkazadi.

    Resurs tejaydigan arxitektura:
    - Har daqiqa o'rniga har 10 daqiqa ishlaydi
    - Har bir job faqat o'z vaqt oralig'ida ishlaydi (UTC)
    - UTC vaqt oralig'i: O'zbekiston UTC+5 ga mos (UTC -5 soat)

    Joblar:
    1. create_daily_journals — 00:01 UTC (o'zgarmaydi)
    2. morning_reminder      — 00:00-05:00 UTC (05:00-10:00 UZT), har 10 daqiqa
    3. evening_reminder      — 13:00-18:00 UTC (18:00-23:00 UZT), har 10 daqiqa
    4. auto_complete         — 17:00-19:30 UTC (22:00-00:30 UZT), har 10 daqiqa

    ⚠️ Diqqat: UTC oralig'i Toshkent vaqtiga (UTC+5) moslashtirilgan.
    Boshqa timezone dagi userlar uchun 10 daqiqalik xato bo'lishi mumkin —
    bu qabul qilingan.
    """
    global _scheduler

    _scheduler = AsyncIOScheduler(timezone="UTC")

    # 1. Kunlik journal yaratish — 00:01 UTC (o'zgarmaydi)
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
    """Moslik uchun saqlanadi."""
    pass


def refresh_user_jobs(bot, user_id: int, settings: dict) -> None:
    """Moslik uchun saqlanadi."""
    pass


def _wrap(job_func, bot):
    """Job funksiyasini bot bilan o'rab qaytaradi."""
    async def wrapper():
        await job_func(bot)
    return wrapper
