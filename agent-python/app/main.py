from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.market_pulse import router as market_pulse_router
from app.api.reports import router as reports_router
from app.config import settings
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
app.include_router(market_pulse_router)
app.include_router(reports_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
