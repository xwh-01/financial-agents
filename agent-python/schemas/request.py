from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    title: str
    content: str
    source: str
    published_at: str
