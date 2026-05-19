from pydantic import BaseModel, Field

from schemas.workflow import WorkflowResult


class SearchNewsRequest(BaseModel):
    query: str
    limit: int = 5
    language: str = "en"
    translate_to_zh: bool = True


class NewsItem(BaseModel):
    index: int | None = None
    title: str
    title_zh: str = ""
    content: str = ""
    content_zh: str = ""
    source: str = ""
    url: str = ""
    published_at: str = ""

    provider: str = ""
    relevance_score: float = 0
    relevance_reasons: list[str] = Field(default_factory=list)
    matched_tickers: list[str] = Field(default_factory=list)
    matched_topics: list[str] = Field(default_factory=list)
    matched_events: list[str] = Field(default_factory=list)


class SearchNewsResponse(BaseModel):
    items: list[NewsItem] = Field(default_factory=list)


class BatchAnalyzeNewsRequest(BaseModel):
    query: str
    limit: int = 3
    language: str = "en"
    translate_to_zh: bool = True


class NewsAnalysisItem(BaseModel):
    news: NewsItem
    analysis_result: WorkflowResult | None = None
    status: str = "completed"
    error_message: str | None = None


class BatchAnalyzeNewsResponse(BaseModel):
    query: str
    total: int
    results: list[NewsAnalysisItem] = Field(default_factory=list)
