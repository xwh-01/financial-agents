import asyncio
import json
from pathlib import Path

from app.agents.graph import MarketPulseWorkflow
from app.core.config import Settings
from app.core.trace import TraceRecorder
from app.eval.metrics import calculate_metrics
from app.schemas import EvalCase, MarketSignal, NewsItem, RankedNewsItem
from app.services.ranking_service import rank_news


def test_config_loads_env_values(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-test")
    monkeypatch.setenv("TRACE_DIR", "tmp-traces")
    settings = Settings()
    assert settings.deepseek_model == "deepseek-test"
    assert settings.trace_dir == "tmp-traces"
    assert settings.llm_model == "deepseek-test"


def test_config_reads_single_root_env_file():
    from app.config import ENV_FILE

    normalized = str(ENV_FILE).replace("\\", "/")
    assert normalized.endswith("financial-agents/.env")


def test_ranking_service_prioritizes_market_news():
    items = [
        NewsItem(
            title="Celebrity attends movie premiere",
            summary="Entertainment news",
            source="Local",
        ),
        NewsItem(
            title="Nvidia revenue beats estimates on AI chip demand",
            summary="Guidance improved for data center revenue.",
            source="Reuters",
            symbol="NVDA",
        ),
    ]
    ranked = rank_news(items, query="Nvidia earnings", tickers=["NVDA"])
    assert ranked[0].symbol == "NVDA"
    assert ranked[0].impact_score > 0
    assert "requested_symbol_match" in ranked[0].reason


def test_trace_file_generation(tmp_path):
    trace = TraceRecorder(trace_id="trace-test", trace_dir=tmp_path)
    span = trace.start_node("RankNewsNode", {"input": 1})
    trace.finish_node(span, {"output": 1}, llm_model=None, token_usage=None)
    path = Path(trace.save())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["trace_id"] == "trace-test"
    assert data["events"][0]["node_name"] == "RankNewsNode"
    assert data["events"][0]["latency_ms"] >= 0


def test_workflow_runs_with_mock_services(tmp_path):
    class FakeNewsService:
        async def fetch_news(self, query, tickers=None, limit=None):
            return [
                NewsItem(
                    title="Apple guidance improves after iPhone demand",
                    summary="Revenue guidance moved higher.",
                    source="Reuters",
                    symbol="AAPL",
                )
            ]

    class FakeLLMService:
        last_model = "fake-model"
        last_token_usage = {"total_tokens": 1}

        async def analyze_impact(self, item):
            return MarketSignal(
                title=item.title,
                summary=item.summary,
                source=item.source,
                symbol=item.symbol,
                impact_score=item.impact_score,
                reason=item.reason,
                risk=item.risk,
                confidence=item.confidence,
            )

    from app.agents.nodes import AnalyzeImpactNode, FetchNewsNode

    workflow = MarketPulseWorkflow(
        fetch_node=FetchNewsNode(FakeNewsService()),
        analyze_node=AnalyzeImpactNode(FakeLLMService()),
    )
    state = asyncio.run(workflow.run("Apple guidance", max_items=3, tickers=["AAPL"]))
    assert state.report is not None
    assert state.report.analyzed_news_count == 1
    assert state.trace_path is not None


def test_eval_metrics_calculation():
    cases = [
        EvalCase(title="Important", expected_important=True),
        EvalCase(title="Noise", expected_important=False),
    ]
    ranked = [
        RankedNewsItem(title="Important", impact_score=10, confidence=0.9),
        RankedNewsItem(title="Noise", impact_score=1, confidence=0.1),
    ]
    metrics = calculate_metrics(ranked, cases, average_latency_ms=2.5)
    assert metrics["Precision@5"] == 0.5
    assert metrics["ImportantRecall@10"] == 1.0
    assert metrics["IrrelevantRate@10"] == 0.5
