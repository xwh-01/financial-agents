import logging

from report_jobs import repository
from report_jobs.service import run_job


logger = logging.getLogger(__name__)


async def run_pending_jobs_once(limit: int = 5) -> int:
    jobs = repository.find_pending_jobs(limit=limit)
    completed = 0

    for job in jobs:
        try:
            await run_job(job["id"])
            completed += 1
        except Exception as exc:
            logger.warning("report job %s failed: %s", job["id"], exc)

    return completed
