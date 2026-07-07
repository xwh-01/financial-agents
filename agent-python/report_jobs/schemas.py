from pydantic import BaseModel


class CreateReportJobRequest(BaseModel):
    job_type: str = "manual"
    scheduled_for: str | None = None


class ReportJobResponse(BaseModel):
    id: int
    user_id: int
    watchlist_id: int
    status: str
    job_type: str
    scheduled_for: str | None = None
    current_step: str | None = None
    progress_current: int = 0
    progress_total: int = 0
    locked_until: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    error_message: str | None = None
    last_error: str | None = None
    report_id: int | None = None
    trace_id: int | None = None
    cancel_requested: bool = False
    created_at: str | None = None
    updated_at: str | None = None
