from market_pulse.schemas import ComplianceResult, ReportResult
from safety.report_guard import check_report_safety


def check_compliance(report_result: ReportResult) -> ComplianceResult:
    return check_report_safety(report_result.content)
