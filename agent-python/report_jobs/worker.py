import asyncio
import logging
import os
import signal
import sys

from report_jobs import repository
from report_jobs.service import run_job

logger = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = 5
DEFAULT_BATCH_LIMIT = 3


async def run_pending_jobs_once(limit: int = DEFAULT_BATCH_LIMIT) -> int:
    jobs = repository.find_pending_jobs(limit=limit)
    completed = 0

    for job in jobs:
        job_id = job["id"]
        if not repository.claim_pending_job(job_id):
            continue

        try:
            await run_job(job_id)
            completed += 1
        except Exception:
            logger.warning("report job %s failed", job_id, exc_info=True)

    return completed


async def run_worker_loop() -> None:
    interval = int(
        os.environ.get(
            "REPORT_JOB_SCAN_INTERVAL_SECONDS",
            str(DEFAULT_SCAN_INTERVAL),
        ),
    )
    logger.info("report job worker started (scan interval=%ss)", interval)

    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("worker received shutdown signal")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    try:
        while not stop_event.is_set():
            try:
                completed = await run_pending_jobs_once()
                if completed:
                    logger.info("worker completed %s job(s)", completed)
            except Exception:
                logger.warning("worker scan failed", exc_info=True)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass
    finally:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, ValueError):
                pass

    logger.info("report job worker stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    )
    try:
        asyncio.run(run_worker_loop())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
