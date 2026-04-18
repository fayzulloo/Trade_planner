from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from scheduler.jobs import send_daily_reminders
from utils.logger import logger
import pytz


def setup_scheduler(bot):
    try:
        timezone = pytz.timezone("UTC")
        scheduler = AsyncIOScheduler(timezone=timezone)
        scheduler.add_job(
            send_daily_reminders,
            trigger=CronTrigger(minute="*", timezone=timezone),
            args=[bot],
            max_instances=1,
            misfire_grace_time=30
        )
        scheduler.start()
        logger.info("Scheduler ishga tushdi.")
        return scheduler
    except Exception as e:
        logger.error(f"Scheduler xatosi: {e}")
        raise
