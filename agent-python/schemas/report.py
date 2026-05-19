from pydantic import BaseModel, Field


class ReportResult(BaseModel):
    content: str
    sections: list[str] = Field(default_factory=list)
