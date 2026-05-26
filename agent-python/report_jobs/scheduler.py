import asyncio
import logging
from datetime import datetime

from app.config import settings
from report_jobs.service import create_daily_jobs_for_all_watchlists
from report_jobs.worker import run_pending_jobs_once


logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []
_started = False


def start_scheduler() -> None:
    global _started
    if _started or not settings.enable_report_scheduler:
        return

    try:
        loop = asyncio.get_running_loop()
        _tasks.append(loop.create_task(_daily_job_loop()))
        _tasks.append(loop.create_task(_worker_loop()))
        _started = True
        logger.info("report scheduler started")
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
    last_run_key = ""
    while True:
        try:
            now = datetime.now()
            run_key = now.strftime("%Y-%m-%d")
            if (
                now.hour == settings.daily_report_hour
                and now.minute == settings.daily_report_minute
                and run_key != last_run_key
            ):
                created = create_daily_jobs_for_all_watchlists()
                last_run_key = run_key
                logger.info("created %s daily report jobs", created)
        except Exception as exc:
            logger.warning("daily report job creation failed: %s", exc)

        await asyncio.sleep(30)


async def _worker_loop() -> None:
    while True:
        try:
            await run_pending_jobs_once(limit=5)
        except Exception as exc:
            logger.warning("pending report job scan failed: %s", exc)

        await asyncio.sleep(settings.report_job_scan_seconds)
