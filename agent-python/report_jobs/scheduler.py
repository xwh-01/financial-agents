import asyncio
import logging
from datetime import date, datetime

from app.config import settings
from report_jobs.service import create_daily_jobs_for_all_watchlists

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []
_started = False


def start_scheduler() -> None:
    global _started
    if _started:
        return
    if not settings.enable_report_scheduler:
        logger.info("report scheduler disabled (ENABLE_REPORT_SCHEDULER=false)")
        return

    try:
        loop = asyncio.get_running_loop()
        _tasks.append(loop.create_task(_daily_job_loop()))
        _started = True
        logger.info(
            "report scheduler started (daily at %02d:%02d)",
            settings.daily_report_hour,
            settings.daily_report_minute,
        )
    except Exception as exc:
        logger.warning("failed to start report scheduler: %s", exc)


async def stop_scheduler() -> None:
    global _started
    if not _tasks:
        _started = False
        return

    for task in _tasks:
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()
    _started = False
    logger.info("report scheduler stopped")


async def _daily_job_loop() -> None:
    last_date: str = ""
    while True:
        try:
            now = datetime.now()
            today = date.today().isoformat()
            if (
                now.hour == settings.daily_report_hour
                and now.minute == settings.daily_report_minute
                and today != last_date
            ):
                created = create_daily_jobs_for_all_watchlists()
                last_date = today
                logger.info("created %s daily report job(s)", created)
        except Exception as exc:
            logger.warning("daily report job creation failed: %s", exc)

        await asyncio.sleep(30)
