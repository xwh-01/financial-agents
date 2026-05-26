from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.market_pulse import router as market_pulse_router
from app.api.report_jobs import router as report_jobs_router
from app.api.reports import router as reports_router
from app.api.watchlists import router as watchlists_router
from app.config import settings
from report_jobs.scheduler import start_scheduler, stop_scheduler
from storage.report_store import init_db


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(market_pulse_router)
app.include_router(reports_router)
app.include_router(watchlists_router)
app.include_router(report_jobs_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    start_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    await stop_scheduler()
