import json
import importlib.util
import sys
import types
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from clients.market_data_client import calculate_returns
from market_pulse.schemas import NewsItem
from market_pulse.filters.news_filter import dedupe_news


ROOT = Path(__file__).resolve().parents[1]


def test_eval_runner_generates_reports():
    spec = importlib.util.spec_from_file_location("root_eval_runner", ROOT / "evals" / "run_eval.py")
    run_eval = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(run_eval)
    run_eval.main()
    report_md = ROOT / "evals" / "report.md"
    report_json = ROOT / "evals" / "report.json"
    assert report_md.exists()
    assert report_json.exists()
    data = json.loads(report_json.read_text(encoding="utf-8"))
    assert data["metrics"]["total_cases"] >= 20
    assert "compliance_violation_rate" in data["metrics"]


def test_rss_dedupe_is_deterministic():
    items = [
        NewsItem(title="Same", url="https://example.com/a"),
        NewsItem(title="Same", url="https://example.com/a"),
        NewsItem(title="Other", url="https://example.com/b"),
    ]
    deduped = dedupe_news(items)
    assert [item.title for item in deduped] == ["Same", "Other"]


def test_market_data_returns_are_deterministic():
    prices = [
        {"date": f"2026-07-{day:02d}", "close": float(100 + day), "volume": 1000 + day}
        for day in range(10, 1, -1)
    ]
    returns = calculate_returns(prices)
    assert returns["return_1d"] is not None
    assert returns["return_3d"] is not None
    assert returns["return_7d"] is not None


def test_langgraph_main_route_smoke_with_mock(monkeypatch):
    if "feedparser" not in sys.modules:
        dummy = types.SimpleNamespace(parse=lambda *_args, **_kwargs: types.SimpleNamespace(feed={}, entries=[]))
        monkeypatch.setitem(sys.modules, "feedparser", dummy)

    async def fake_run_langgraph_market_pulse(query, max_items=8, tickers=None):
        return {
            "status": "completed",
            "query": query,
            "workflow": "langgraph_market_pulse",
            "trace_id": "trace-test",
            "market_signals": [
                {
                    "signal_id": "signal-001-NVDA",
                    "title": "NVDA 市场观察信号",
                    "summary": "mock",
                    "supporting_articles": [
                        {
                            "title": "Mock article",
                            "source": "MockWire",
                            "url": "https://example.com/mock",
                            "published_at": "2026-07-01T00:00:00Z",
                            "reason": "mock evidence",
                            "relevance_score": 1.0,
                        }
                    ],
                }
            ],
        }

    import app.api.market_pulse as market_pulse_api

    monkeypatch.setattr(
        market_pulse_api,
        "run_langgraph_market_pulse",
        fake_run_langgraph_market_pulse,
    )
    test_app = FastAPI()
    test_app.include_router(market_pulse_api.router)
    client = TestClient(test_app)
    response = client.post(
        "/api/agent/market-pulse/langgraph",
        json={"query": "NVIDIA AI chips", "max_items": 3, "tickers": ["NVDA"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["trace_id"] == "trace-test"
    assert data["market_signals"][0]["supporting_articles"]
