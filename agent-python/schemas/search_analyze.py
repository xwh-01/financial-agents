from pydantic import BaseModel

from schemas.news import NewsItem
from schemas.workflow import WorkflowResult


class SearchAndAnalyzeRequest(BaseModel):
    query: str
    limit: int = 5
    language: str = "en"


class SearchAndAnalyzeResponse(BaseModel):
    selected_news: NewsItem | None = None
    analysis_result: WorkflowResult | None = None
    message: str = ""
