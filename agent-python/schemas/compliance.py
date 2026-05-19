from pydantic import BaseModel, Field


class ComplianceResult(BaseModel):
    passed: bool
    violations: list[str] = Field(default_factory=list)
    required_disclaimer_present: bool
    sanitized_report: str
