from market_pulse.analyzers.report_generator import build_market_signals
from market_pulse.schemas import (
    DailyNewsAnalysis,
    EntityResult,
    EventResult,
    NewsItem,
    RiskResult,
    TickerLinks,
    WorkflowResult,
)
from safety.compliance import apply_output_compliance_guard, sanitize_text


def _analysis_item() -> DailyNewsAnalysis:
    news = NewsItem(
        index=1,
        title="Nvidia AI chip demand remains strong",
        content="Cloud customers keep ordering GPUs.",
        source="MockWire",
        url="https://example.com/nvda",
        published_at="2026-07-01T13:00:00Z",
        relevance_score=0.92,
        matched_tickers=["NVDA"],
    )
    result = WorkflowResult(
        task_id="t1",
        status="completed",
        entity_result=EntityResult(companies=["Nvidia"], tickers=["NVDA"], confidence=0.9),
        event_result=EventResult(
            event_type="industry_demand",
            summary="AI chip demand remains strong",
            sentiment="positive",
            impact_score=0.8,
            confidence=0.8,
        ),
        ticker_links=TickerLinks(
            direct_tickers=["NVDA"],
            reason="Nvidia is named directly in the article.",
            confidence=0.9,
        ),
        risk_result=RiskResult(risk_level="low", risk_flags=[], reason="No major risk flag."),
        report="Nvidia AI demand observation",
    )
    return DailyNewsAnalysis(news=news, analysis_result=result)


def test_compliance_guard_sanitizes_buy_sell_language():
    sanitized, violations = sanitize_text("建议买入 NVDA，稳赚且保证收益。")
    assert violations
    assert "建议买入" not in sanitized
    assert "稳赚" not in sanitized
    assert "保证收益" not in sanitized


def test_market_signal_schema_contains_supporting_articles():
    from market_pulse.analyzers.report_generator import predict_ticker_trends

    item = _analysis_item()
    trends = predict_ticker_trends([item.analysis_result])
    signals = build_market_signals(trends, [item])
    assert signals
    signal = signals[0]
    assert signal.supporting_articles
    assert signal.supporting_articles[0].url == "https://example.com/nvda"


def test_output_guard_marks_signal_violation_and_adds_disclaimer():
    guarded = apply_output_compliance_guard(
        {
            "report": "建议买入，保证收益。",
            "market_signals": [
                {
                    "signal_id": "s1",
                    "title": "建议买入",
                    "summary": "稳赚",
                    "risk_level": "low",
                    "supporting_articles": [],
                }
            ],
        }
    )
    assert guarded["disclaimer"]
    assert guarded["compliance_status"] == "warning"
    assert guarded["market_signals"][0]["signal_type"] == "risk_observation"


def test_generate_report_no_longer_requires_unsupported_recommendation_only_output():
    from market_pulse.analyzers.report_generator import build_market_signal_report

    item = _analysis_item()
    from market_pulse.analyzers.report_generator import predict_ticker_trends

    trends = predict_ticker_trends([item.analysis_result])
    signals = build_market_signals(trends, [item])
    report = build_market_signal_report(signals)
    assert "市场观察信号" in report
    assert "相关来源" in report
    assert "建议买入" not in report
