from schemas.compliance import ComplianceResult
from safety.forbidden_phrases import FORBIDDEN_PHRASES
from safety.policy import REQUIRED_DISCLAIMER


def check_report_safety(report: str) -> ComplianceResult:
    violations: list[str] = []

    for phrase in FORBIDDEN_PHRASES:
        if phrase in report:
            violations.append(phrase)

    sanitized_report = report

    if REQUIRED_DISCLAIMER not in sanitized_report:
        sanitized_report += (
            "\n\n免责声明：本报告仅用于舆情事件分析与学习展示，不构成投资建议。"
        )

    if violations:
        sanitized_report += "\n\n合规提示：报告中检测到可能构成投资建议或收益承诺的表达，请重新生成或人工复核。"

    final_disclaimer_present = REQUIRED_DISCLAIMER in sanitized_report

    return ComplianceResult(
        passed=final_disclaimer_present and len(violations) == 0,
        violations=violations,
        required_disclaimer_present=final_disclaimer_present,
        sanitized_report=sanitized_report,
    )
