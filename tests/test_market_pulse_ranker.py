from datetime import datetime, timezone

from market_pulse.rankers.news_ranker import (
    filter_and_rank_news,
    select_representative_news,
)
from market_pulse.rankers.query_driven_ranker import coarse_filter
from market_pulse.schemas import NewsItem


def _news(title: str, content: str, source: str = "Reuters") -> NewsItem:
    return NewsItem(
        title=title,
        content=content,
        source=source,
        published_at=datetime.now(timezone.utc).isoformat(),
    )


# ---- legacy ranker tests (backward compat) ----

def test_watchlist_ranker_recalls_and_selects_multiple_intents():
    query = (
        "Market Pulse for watchlist Growth:\n"
        "tickers: NVDA, TSLA\n"
        "topics: AI chips, robotaxi\n"
        "macro: Fed rates"
    )
    items = [
        _news(
            "Nvidia data center GPU demand lifts AI chip revenue outlook",
            "Cloud customers increased orders for AI accelerators and data center GPUs.",
        ),
        _news(
            "Tesla robotaxi timeline faces regulatory review",
            "Analysts are watching robotaxi approval timing, deliveries, and EV margins.",
        ),
        _news(
            "Fed officials signal rate cuts may be delayed",
            "Treasury yields rose as inflation data changed expectations for interest rates.",
        ),
        _news(
            "Local computer store discounts gaming accessories",
            "A weekend sale includes keyboards and consumer graphics cards.",
            source="Local",
        ),
    ]

    ranked = filter_and_rank_news(items, query=query)
    selected = select_representative_news(
        ranked,
        limit=3,
        requested_tickers=["NVDA", "TSLA"],
    )

    titles = [item.title for item in selected]
    assert any("Nvidia" in title for title in titles)
    assert any("Tesla" in title for title in titles)
    assert any("Fed" in title for title in titles)
    assert all("gaming accessories" not in title for title in titles)


def test_watchlist_ranker_hard_filters_stale_news():
    stale = NewsItem(
        title="Nvidia announces older AI chip platform",
        content="Data center GPU demand improved.",
        source="Reuters",
        published_at="2020-01-01T00:00:00Z",
    )
    fresh = _news(
        "Nvidia announces new AI chip platform",
        "Data center GPU revenue and AI accelerator demand improved.",
    )

    ranked = filter_and_rank_news(
        [stale, fresh],
        query="tickers: NVDA\ntopics: AI chips",
    )

    assert [item.title for item in ranked] == [fresh.title]


# ---- layer-1 coarse filter tests ----

def test_coarse_filter_per_intent_recall():
    """Multi-intent query: NVDA dominates in count but TSLA must still appear."""
    query = "tickers: NVDA, TSLA\ntopics: AI chips"
    items = [
        _news("Nvidia GPU sales double on AI chip demand",
              "Nvidia data center revenue surged as cloud providers expand AI compute."),
        _news("Nvidia Blackwell platform sets new performance records",
              "The new Blackwell architecture delivers 4x training performance."),
        _news("Nvidia partners with major cloud providers for AI expansion",
              "AWS, Azure, and Google Cloud adopt Nvidia H200 GPUs."),
        _news("Nvidia stock hits all-time high on earnings beat",
              "NVDA shares surged after strong quarterly results."),
        _news("Nvidia CEO highlights AI factory vision at GTC",
              "Jensen Huang outlined a roadmap for AI infrastructure."),
        _news("Nvidia expands autonomous driving partnerships",
              "Nvidia Drive platform adopted by multiple automakers."),
        _news("Tesla deliveries beat expectations for Q3",
              "EV maker Tesla delivered more vehicles than analysts projected."),
    ]

    result = coarse_filter(items, query=query)

    titles = [item.title for item in result]
    assert any("Tesla" in title for title in titles), (
        f"TSLA should appear despite NVDA dominating the candidate pool. Got: {titles}"
    )
    assert any("Nvidia" in title for title in titles)


def test_coarse_filter_three_intents_all_present():
    """NVDA, TSLA, and Fed each get guaranteed recall slots."""
    query = "tickers: NVDA, TSLA\nmacro: Fed rates"
    items = (
        [_news(f"Nvidia news {i}", "AI chips GPUs data center growth.", "Reuters")
         for i in range(10)]
        + [_news("Tesla robotaxi delayed", "Regulatory hurdles slow Tesla rollout.")]
        + [_news("Fed holds rates steady", "Federal Reserve keeps benchmark unchanged.")]
    )

    result = coarse_filter(items, query=query)
    titles = [item.title for item in result]

    assert any("Tesla" in title for title in titles), (
        f"TSLA recall missing: {titles[:5]}"
    )
    assert any("Fed" in title for title in titles), (
        f"Fed recall missing: {titles[:5]}"
    )


def test_coarse_filter_hard_filters_stale_news():
    stale = NewsItem(
        title="Nvidia announces older AI chip platform",
        content="Data center GPU demand improved.",
        source="Reuters",
        published_at="2020-01-01T00:00:00Z",
    )
    fresh = _news("Nvidia launches new AI chip",
                  "Data center GPU revenue improved with AI accelerator demand.")

    result = coarse_filter([stale, fresh], query="NVDA AI chip")

    assert [item.title for item in result] == [fresh.title]


def test_coarse_filter_empty_query_fallback():
    items = [
        _news("Old news about markets", "General market commentary.", source="Local"),
        _news("Breaking: AI chip breakthrough", "New semiconductor process.", source="Reuters"),
    ]
    result = coarse_filter(items, query="")
    assert len(result) <= len(items)
    assert result[0].source == "Reuters"


def test_coarse_filter_single_intent_no_explosion():
    """With a single intent, just return top items normally."""
    query = "tickers: NVDA"
    items = [_news(f"Nvidia news {i}", "AI chips growth.", "Reuters") for i in range(5)]

    result = coarse_filter(items, query=query)
    assert len(result) == 5
    assert all("Nvidia" in item.title for item in result)
