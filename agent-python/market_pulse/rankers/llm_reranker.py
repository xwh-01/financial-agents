"""Layer 3: LLM re-rank. Single LLM call to select top-8 from ~15 candidates."""

import json
import logging
import re

from clients.llm_client import chat_completion
from market_pulse.schemas import NewsItem

logger = logging.getLogger(__name__)

LLM_RERANK_LIMIT = 8

RE_RANK_SYSTEM_PROMPT = """\
You are a financial news relevance judge. Given a user query and a list of \
candidate news articles, select the most relevant ones.

Return ONLY a JSON array of the candidate numbers (1-based index) that are \
most relevant to the query, ordered from most to least relevant.

For example: [3, 7, 1, 12, 5, 8, 2, 10]

Rules:
- Select at most {limit} candidates.
- The query may contain multiple topics, tickers, or themes. You MUST ensure \
every distinct topic/ticker/theme in the query is covered by at least one \
selected article. Do not let a single topic dominate the entire selection.
- Prioritize news that directly addresses the query's topics, tickers, or themes.
- Avoid selecting multiple articles about the exact same event.
- Skip articles that are clearly irrelevant.
- Return ONLY the JSON array, no other text."""


async def llm_rerank(
    items: list[NewsItem],
    query: str,
    limit: int = LLM_RERANK_LIMIT,
) -> list[NewsItem]:
    """
    Layer 3 LLM re-rank — single LLM call to pick the top ~8 most relevant
    articles from ~15 candidates.

    The prompt instructs the LLM to ensure every distinct topic/ticker/theme
    in the query is covered by at least one selected article, preventing a
    single dominant theme from monopolizing the final selection.

    If the LLM call fails or returns unparseable output, falls back to taking
    the first `limit` items.
    """
    if not items:
        return []
    if len(items) <= limit:
        return items

    try:
        prompt = _build_rerank_prompt(items, query, limit)
        system = RE_RANK_SYSTEM_PROMPT.format(limit=limit)
        response = await chat_completion(system_prompt=system, user_prompt=prompt)
        indices = _parse_indices(response, len(items), limit)
        if indices:
            return [items[i] for i in indices if i < len(items)]
    except Exception:
        logger.warning("llm_rerank: LLM call failed, falling back to truncation", exc_info=True)

    return items[:limit]


def _build_rerank_prompt(items: list[NewsItem], query: str, limit: int) -> str:
    lines = [f"User Query: {query}", "", "Candidates:"]
    for i, item in enumerate(items, start=1):
        title = item.title or "(no title)"
        source = item.source or "unknown"
        content_preview = (item.content or "")[:200].replace("\n", " ")
        lines.append(f"{i}. [{source}] {title}")
        if content_preview:
            lines.append(f"   {content_preview}")
        lines.append("")

    lines.append(f"Select the top {limit} most relevant candidates.")
    return "\n".join(lines)


def _parse_indices(response: str, max_items: int, limit: int) -> list[int] | None:
    text = response.strip()
    try:
        match = re.search(r"\[[\d,\s]+\]", text)
        if match:
            arr = json.loads(match.group())
            indices = [
                int(x) - 1
                for x in arr
                if isinstance(x, (int, float)) and 1 <= int(x) <= max_items
            ]
            if indices:
                return indices[:limit]
    except (json.JSONDecodeError, ValueError):
        pass

    numbers = [
        int(x) - 1
        for x in re.findall(r"\b(\d+)\b", text)
        if 1 <= int(x) <= max_items
    ]
    if numbers:
        return numbers[:limit]

    return None
