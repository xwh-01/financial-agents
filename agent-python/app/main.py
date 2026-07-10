from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.market_pulse import router as market_pulse_router
from app.api.opportunities import router as opportunities_router
from app.api.report_jobs import router as report_jobs_router
from app.api.reports import router as reports_router
from app.api.watchlists import router as watchlists_router
from app.config import settings
from auth.security import validate_security_settings
from report_jobs.scheduler import start_scheduler, stop_scheduler
from storage.report_store import init_db


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

_cors_origins = [
    o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()
] or ["http://127.0.0.1:5173", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(market_pulse_router, tags=["market_pulse"])
app.include_router(opportunities_router, tags=["opportunities"])
app.include_router(reports_router, tags=["reports"])
app.include_router(watchlists_router, tags=["watchlists"])
app.include_router(report_jobs_router, tags=["report_jobs"])


@app.on_event("startup")
def startup() -> None:
    """
    Application startup hook.

    1. Validates that security settings (JWT secret, etc.) are not using dev defaults
       in non-development environments.
    2. Initializes the SQLite database and applies any pending schema migrations.
    3. Starts the daily report job scheduler background task (if enabled).
    """
    validate_security_settings()
    init_db()
    start_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    await stop_scheduler()
