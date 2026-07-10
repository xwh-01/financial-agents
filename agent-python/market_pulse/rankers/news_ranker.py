import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from market_pulse.rankers.source_weight import get_source_weight
from market_pulse.schemas import NewsItem


RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "ranker_rules.json"
INTENT_RECALL_LIMIT = 20

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "market",
    "news",
    "of",
    "on",
    "or",
    "pulse",
    "the",
    "to",
    "watchlist",
    "what",
    "with",
}

DEFAULT_RULES: dict[str, Any] = {
    "weights": {
        "event_match": 3.0,
        "ticker_match": 4.0,
        "topic_match": 2.0,
        "market_term_cap": 4.0,
        "query_boost_per_hit": 2.0,
        "query_boost_cap": 6.0,
        "query_hit_per_token": 4.0,
        "query_hit_cap": 16.0,
        "context_hit": 3.0,
        "context_hit_cap": 12.0,
        "source_multiplier": 2.0,
        "strong_negative": -5.0,
        "weak_negative": -2.0,
        "query_weak_negative": -3.0,
        "bad_term": -5.0,
        "content_too_short": -1.0,
        "low_quality_surface": -5.0,
    },
    "freshness": {
        "max_age_days": 7,
        "missing": -1.5,
        "future": 3.0,
        "within_6h": 3.0,
        "within_24h": 2.0,
        "within_72h": 1.0,
        "within_max_age": 0.25,
        "too_old": -10.0,
    },
    "tickers": {},
    "events": {},
    "topics": {},
    "market_terms": [],
    "negative_terms": {"bad": [], "strong": [], "weak": [], "low_quality_surface": []},
    "query_profiles": {},
    "context_rules": {},
    "special_penalties": [],
}


@lru_cache(maxsize=1)
def _rules() -> dict[str, Any]:
    """
    加载排名规则配置（config/ranker_rules.json），与 DEFAULT_RULES 深度合并。

    进程生命周期内仅加载一次（lru_cache），配置文件为静态内容。
    若配置文件缺失或不可读，则回退到 DEFAULT_RULES。
    """
    try:
        with open(RULES_PATH, encoding="utf-8") as fh:
            loaded = json.load(fh)
    except OSError:
        return DEFAULT_RULES
    return _deep_merge(DEFAULT_RULES, loaded)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """递归合并配置：override 中的字典键会深层合并，而非整体替换，保证用户只覆写关心的字段。"""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def parse_news_time(value: str | None) -> datetime | None:
    """
    将新闻时间戳字符串解析为带 UTC 时区的 datetime。

    支持的格式：
      - ISO 8601（含/不含时区，含/不含末尾 Z）
      - RFC 2822（通过 email.utils.parsedate_to_datetime）

    缺失、为空或无法解析时返回 None。所有返回值统一归一化到 UTC。
    """
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass

    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def is_recent_news(item: NewsItem, max_age_days: int | None = None) -> bool:
    """
    检查新闻条目是否在配置的最大时效窗口内。

    时间戳无法解析的条目保留（假定为最新）。最大天数从 ranker_rules.json
    的 freshness.max_age_days 读取，默认 7 天。
    """
    rules = _rules()
    max_days = max_age_days or int(rules["freshness"].get("max_age_days", 7))
    published = parse_news_time(item.published_at)
    if not published:
        return True
    age = datetime.now(timezone.utc) - published
    return age.days <= max_days


def freshness_score(item: NewsItem) -> float:
    """
    根据新闻发布时间计算新鲜度得分 — 越新分越高，过旧大幅扣分。

    评分层级（可通过 ranker_rules.json 配置）：
      - 时间戳缺失：小幅扣分（默认 -1.5），保留在候选池中
      - 未来时间戳（时钟偏差）：按最新处理（默认 3.0），避免掉入负分
      - 6 小时内：最大新鲜度加成（默认 3.0）
      - 24h / 72h / 最大时效内：逐级递减的加成
      - 超过 max_age_days：大幅扣分（默认 -10.0），实际相当于剔除
    """
    rules = _rules()
    config = rules["freshness"]
    published = parse_news_time(item.published_at)
    if not published:
            # 时间戳缺失或无法解析 — 小幅扣分，不直接丢弃
            return float(config.get("missing", -1.5))

    hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
    if hours < 0:
            # 发布时间戳为未来时间（时钟偏差 / 时区错误），当超新鲜处理，避免掉入负分
        return float(config.get("future", 3.0))
    if hours <= 6:
        return float(config.get("within_6h", 3.0))
    if hours <= 24:
        return float(config.get("within_24h", 2.0))
    if hours <= 72:
        return float(config.get("within_72h", 1.0))
    if hours <= 24 * int(config.get("max_age_days", 7)):
        return float(config.get("within_max_age", 0.25))
    return float(config.get("too_old", -10.0))


def filter_and_rank_news(
    items: list[NewsItem],
    min_score: float = 3,
    query: str = "",
) -> list[NewsItem]:
    """
    旧版（非 LangGraph）排名路径：硬过滤 -> 按意图召回 -> 混合排名。

    步骤：
      1. 硬过滤 + 去重（剔除空标题、过旧、内容过短、重复条目）
      2. 将 query 解析为观察列表意图组（如 ticker:/topic: 行）
      3. 用关键词匹配对每条候选新闻针对所有意图打分
      4. 按意图召回：每个意图可取 INTENT_RECALL_LIMIT 条最高分，
         防止单一主题霸占全部结果
      5. 取所有意图召回结果的交集，按总分降序排列

    用于旧版 market_pulse 和 daily_brief 服务路径。
    LangGraph 路径使用三层管道（query_driven -> embedding -> llm）。
    """
    rules = _rules()
    intents = _parse_watchlist_intents(query)
    deduped = _hard_filter_and_dedupe(items, query, rules)
    if not deduped:
        return []

    scored_records: list[dict[str, Any]] = []
    for item in deduped:
        record = _score_candidate(item, intents, query, rules)
        if record["score"] >= min_score:
            scored_records.append(record)

    if not scored_records:
        return []

    recalled_keys: set[str] = set()
    for intent_index in range(len(intents)):
        intent_records = [
            record
            for record in scored_records
            if record["intent_scores"][intent_index] > 0
        ]
        intent_records.sort(
            key=lambda record: (
                record["intent_scores"][intent_index],
                record["score"],
                _published_timestamp(record["item"]),
            ),
            reverse=True,
        )
        recalled_keys.update(record["key"] for record in intent_records[:INTENT_RECALL_LIMIT])

    if not recalled_keys:
        recalled_keys = {record["key"] for record in scored_records}

    ranked_records = [record for record in scored_records if record["key"] in recalled_keys]
    ranked_records.sort(
        key=lambda record: (
            record["score"],
            record["item"].source_weight,
            _published_timestamp(record["item"]),
        ),
        reverse=True,
    )
    return [record["item"] for record in ranked_records]


def select_representative_news(
    ranked_news: list[NewsItem],
    limit: int,
    requested_tickers: list[str] | None = None,
    per_ticker: int = 2,
) -> list[NewsItem]:
    """
    从已排名新闻中选出最终送入 LLM 分析的批次，同时保证多样性。

    三轮选取：
      1. 保证每个显式请求的 ticker 至少有 1 篇文章入选
      2. 按最优条目填充（严格限制来源、ticker、主题的重复次数）
      3. 不设上限地填补剩余名额

    确保最终 LLM 批次不会被单一事件或来源霸占。
    """
    if limit <= 0:
        return []
    if len(ranked_news) <= limit:
        return ranked_news[:limit]

    selected: list[NewsItem] = []
    selected_keys: set[str] = set()
    ticker_counts: dict[str, int] = defaultdict(int)
    topic_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    requested = _dedupe_upper(requested_tickers or [])

    def add(item: NewsItem, strict: bool = True) -> bool:
        # strict=True 时执行来源/ticker/主题数量上限控制，防止重复。
        # strict=False 时跳过上限检查，用于 ticker 保证轮次和最终填充轮次。
        if len(selected) >= limit:
            return False
        key = _news_key(item)
        if key in selected_keys:
            return False

        source_key = _normalize_source(item.source, item.url)
        tickers = _dedupe_upper(item.matched_tickers)
        topics = _dedupe_lower(item.matched_topics)

        if strict:
            if source_key and source_counts[source_key] >= max(2, math.ceil(limit / 3)):
                return False
            if tickers and all(ticker_counts[t] >= per_ticker for t in tickers):
                return False
            if topics and all(topic_counts[t] >= max(2, math.ceil(limit / 3)) for t in topics):
                return False

        selected.append(item)
        selected_keys.add(key)
        for ticker in tickers:
            ticker_counts[ticker] += 1
        for topic in topics:
            topic_counts[topic] += 1
        if source_key:
            source_counts[source_key] += 1
        return True

    for ticker in requested:
        for item in ranked_news:
            if ticker in _dedupe_upper(item.matched_tickers) and add(item, strict=False):
                break

    for item in ranked_news:
        add(item, strict=True)

    for item in ranked_news:
        add(item, strict=False)

    return selected[:limit]


def _hard_filter_and_dedupe(
    items: list[NewsItem],
    query: str,
    rules: dict[str, Any],
) -> list[NewsItem]:
    """
    剔除未通过硬过滤的条目（无标题、过旧、过短、仅有负面信号而无市场/查询信号
    抵消），并按 _news_key 去重。
    """
    seen: set[str] = set()
    result: list[NewsItem] = []
    for item in items:
        if not _passes_hard_filter(item, query, rules):
            continue
        key = _news_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _passes_hard_filter(item: NewsItem, query: str, rules: dict[str, Any]) -> bool:
    """
    硬过滤关卡：拒绝空白条目、过旧、过短、或命中强负向/低质量表面词且
    无任何市场信号或查询相关性来抵消的条目。
    """
    title = (item.title or "").strip()
    if not title:
        return False
    if not is_recent_news(item):
        return False

    text = _item_text(item)
    if len(text) < 20:
        return False

    negative_terms = rules.get("negative_terms", {})
    strong_hits = _matched_terms(text, negative_terms.get("strong", []))
    if strong_hits and not _has_market_or_query_signal(text, query, rules):
        return False

    low_quality_hits = _matched_terms(text, negative_terms.get("low_quality_surface", []))
    if low_quality_hits and not _has_market_or_query_signal(text, query, rules):
        return False

    return True


def _score_candidate(
    item: NewsItem,
    intents: list[dict[str, Any]],
    query: str,
    rules: dict[str, Any],
) -> dict[str, Any]:
    """
    计算单条新闻的综合相关性得分。

    公式：基础信号 + 最高意图分 + 0.35×次高意图分
          + 来源权重×来源乘数 + 新鲜度 + 负向罚分。

    返回一个 dict，包含已标注的条目及每条意图的分项得分，供下游召回交集使用。
    """
    text = _item_text(item)
    weights = rules["weights"]

    base = _base_signal_score(item, text, rules)
    source = get_source_weight(item.source, item.url)
    fresh = freshness_score(item)
    negative_score, negative_reasons = _negative_score(text, query, rules)

    intent_scores: list[float] = []
    intent_reasons: list[str] = []
    best_intent_score = 0.0
    second_intent_score = 0.0

    for intent in intents:
        score, reasons = _intent_score(text, intent, base, rules)
        intent_scores.append(score)
        if score > best_intent_score:
            second_intent_score = best_intent_score
            best_intent_score = score
        elif score > second_intent_score:
            second_intent_score = score
        intent_reasons.extend(reasons)

    score = (
        base["score"]
        + best_intent_score
        + second_intent_score * 0.35
        + source * float(weights.get("source_multiplier", 2.0))
        + fresh
        + negative_score
    )

    item.relevance_score = round(score, 4)
    item.source_weight = round(source, 4)
    item.freshness_score = round(fresh, 4)
    item.negative_score = round(negative_score, 4)
    item.matched_tickers = _dedupe_upper(base["tickers"])
    item.matched_topics = _dedupe_lower(base["topics"])
    item.matched_events = _dedupe_lower(base["events"])
    item.negative_reasons = negative_reasons
    item.relevance_reasons = _compact_reasons(
        base["reasons"]
        + intent_reasons
        + [f"source_weight={source:.2f}", f"freshness_score={fresh:.2f}"]
    )

    return {
        "key": _news_key(item),
        "item": item,
        "score": score,
        "intent_scores": intent_scores,
    }


def _base_signal_score(
    item: NewsItem,
    text: str,
    rules: dict[str, Any],
) -> dict[str, Any]:
    """
    与查询无关的基础信号得分：来自词表匹配（ticker/topic/event/market_term），
    以及短文内容的扣分。
    """
    weights = rules["weights"]
    score = 0.0
    reasons: list[str] = []

    tickers = _matched_catalog_labels(text, rules.get("tickers", {}))
    topics = _matched_catalog_labels(text, rules.get("topics", {}))
    events = _matched_catalog_labels(text, rules.get("events", {}))
    market_hits = _matched_terms(text, rules.get("market_terms", []))

    if tickers:
        score += len(tickers) * float(weights.get("ticker_match", 4.0))
        reasons.append("ticker_match:" + ",".join(tickers[:4]))
    if topics:
        score += len(topics) * float(weights.get("topic_match", 2.0))
        reasons.append("topic_match:" + ",".join(topics[:4]))
    if events:
        score += len(events) * float(weights.get("event_match", 3.0))
        reasons.append("event_match:" + ",".join(events[:4]))
    if market_hits:
        market_score = min(
            len(market_hits),
            float(weights.get("market_term_cap", 4.0)),
        )
        score += market_score
        reasons.append("market_terms:" + ",".join(market_hits[:5]))

    if len((item.content or "").strip()) < 80:
        score += float(weights.get("content_too_short", -1.0))
        reasons.append("short_content_penalty")

    return {
        "score": score,
        "reasons": reasons,
        "tickers": tickers,
        "topics": topics,
        "events": events,
        "market_hits": market_hits,
    }


def _intent_score(
    text: str,
    intent: dict[str, Any],
    base: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[float, list[str]]:
    """
    计算一篇文章与单个观察列表意图行的匹配得分。

    由三部分组成：词级查询命中 → profile 加成词命中 → 需要 topic/event/profile
    交叉匹配的上下文规则命中。
    """
    weights = rules["weights"]
    intent_text = intent["text"]
    score = 0.0
    reasons: list[str] = []

    query_hits = _query_hits(text, intent_text)
    if query_hits:
        hit_score = min(
            len(query_hits) * float(weights.get("query_hit_per_token", 4.0)),
            float(weights.get("query_hit_cap", 16.0)),
        )
        score += hit_score
        reasons.append(f"intent:{intent['kind']}:" + ",".join(query_hits[:5]))

    profiles = _query_profiles(intent_text, rules)
    boost_hits = _profile_boost_hits(text, profiles, rules)
    if boost_hits:
        boost_score = min(
            len(boost_hits) * float(weights.get("query_boost_per_hit", 2.0)),
            float(weights.get("query_boost_cap", 6.0)),
        )
        score += boost_score
        reasons.append("profile_boost:" + ",".join(boost_hits[:5]))

    context_hits = _context_hits(
        text=text,
        query_text=intent_text,
        profiles=profiles,
        topics=base["topics"],
        events=base["events"],
        rules=rules,
    )
    if context_hits:
        context_score = min(
            len(context_hits) * float(weights.get("context_hit", 3.0)),
            float(weights.get("context_hit_cap", 12.0)),
        )
        score += context_score
        reasons.append("context:" + ",".join(context_hits[:4]))

    return score, reasons


def _negative_score(
    text: str,
    query: str,
    rules: dict[str, Any],
) -> tuple[float, list[str]]:
    """
    计算负向词匹配的分数惩罚。

    按严重程度依次检查：坏词 → 强负向 → 弱负向 → 低质量表面词 → 查询 profile
    弱负向词 → 特殊惩罚规则（每条规则可按查询条件配置）。
    """
    weights = rules["weights"]
    negative_terms = rules.get("negative_terms", {})
    score = 0.0
    reasons: list[str] = []

    for group_name, weight_key in (
        ("bad", "bad_term"),
        ("strong", "strong_negative"),
        ("weak", "weak_negative"),
        ("low_quality_surface", "low_quality_surface"),
    ):
        hits = _matched_terms(text, negative_terms.get(group_name, []))
        if hits:
            score += len(hits) * float(weights.get(weight_key, 0.0))
            reasons.append(f"{group_name}:" + ",".join(hits[:4]))

    profiles = _query_profiles(query, rules)
    query_weak_hits = _profile_weak_negative_hits(text, profiles, rules)
    if query_weak_hits:
        score += len(query_weak_hits) * float(weights.get("query_weak_negative", -3.0))
        reasons.append("query_weak_negative:" + ",".join(query_weak_hits[:4]))

    for penalty in rules.get("special_penalties", []):
        if _penalty_applies(text, query, penalty):
            value = float(penalty.get("penalty", 0.0))
            score += value
            reasons.append(f"{penalty.get('name', 'special_penalty')}={value:.1f}")

    return score, reasons


def _parse_watchlist_intents(query: str) -> list[dict[str, Any]]:
    """
    将结构化观察列表查询字符串解析为意图行列表。

    期望格式（每行一条）：
      ticker: AAPL
      topic: AI
      company: Nvidia
      macro: CPI
      commodity: gold
      custom: 任意自由文本

    若无结构化行，则回退为按逗号/分号/竖线/and 分割。
    全部失败时，默认使用一个宽泛的市场意图兜底。
    """
    text = (query or "").strip()
    intents: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("market pulse for watchlist"):
            continue
        match = re.match(r"^([A-Za-z_ ]{2,30}):\s*(.+)$", line)
        if not match:
            continue
        kind = match.group(1).strip().lower().replace(" ", "_")
        value = match.group(2).strip()
        if not value:
            continue
        terms = [part.strip() for part in re.split(r"[,;/|]", value) if part.strip()]
        for term in terms or [value]:
            intents.append({"kind": kind, "text": term, "raw": value})

    if not intents and text:
        parts = [part.strip() for part in re.split(r"[,;/|]|\band\b", text) if part.strip()]
        intents = [{"kind": "query", "text": part, "raw": text} for part in parts[:8]]

    if not intents:
        intents = [{"kind": "market", "text": "market earnings inflation stocks", "raw": ""}]

    return intents


def _query_profiles(query_text: str, rules: dict[str, Any]) -> list[str]:
    """将查询文本与 profile 触发器匹配，以激活对应的 boost 词/弱负向词规则集。"""
    profiles: list[str] = []
    for name, profile in rules.get("query_profiles", {}).items():
        if _matched_terms(query_text, profile.get("triggers", [])):
            profiles.append(name)
    return profiles


def _profile_boost_hits(
    text: str,
    profiles: list[str],
    rules: dict[str, Any],
) -> list[str]:
    """在文章文本中找出与当前激活的查询 profile 匹配的加成词。"""
    hits: list[str] = []
    for name in profiles:
        profile = rules.get("query_profiles", {}).get(name, {})
        hits.extend(_matched_terms(text, profile.get("boost_terms", [])))
    return _dedupe_lower(hits)


def _profile_weak_negative_hits(
    text: str,
    profiles: list[str],
    rules: dict[str, Any],
) -> list[str]:
    """在文章文本中找出与当前激活的查询 profile 匹配的弱负向词。"""
    hits: list[str] = []
    for name in profiles:
        profile = rules.get("query_profiles", {}).get(name, {})
        hits.extend(_matched_terms(text, profile.get("weak_negative_terms", [])))
    return _dedupe_lower(hits)


def _context_hits(
    text: str,
    query_text: str,
    profiles: list[str],
    topics: list[str],
    events: list[str],
    rules: dict[str, Any],
) -> list[str]:
    """
    匹配上下文规则：要求 profile、查询词、topic、event 和文章正文满足
    特定的组合条件，同时支持排除模式（text_not/query_terms_not）。
    """
    hits: list[str] = []
    profile_set = set(profiles)
    topic_set = set(topics)
    event_set = set(events)

    for name, rule in rules.get("context_rules", {}).items():
        if rule.get("profiles") and not profile_set.intersection(rule["profiles"]):
            continue
        if rule.get("query_terms_any") and not _matched_terms(
            query_text,
            rule["query_terms_any"],
        ):
            continue
        if rule.get("topics_any") and not topic_set.intersection(rule["topics_any"]):
            continue
        if rule.get("events_any") and not event_set.intersection(rule["events_any"]):
            continue
        if rule.get("text_any") and not _matched_terms(text, rule["text_any"]):
            continue
        if rule.get("text_not") and _matched_terms(text, rule["text_not"]):
            continue
        hits.append(name)
    return hits


def _penalty_applies(text: str, query: str, penalty: dict[str, Any]) -> bool:
    """检查给定的特殊惩罚规则是否对当前查询+文本组合触发。"""
    if penalty.get("query_terms_any") and not _matched_terms(
        query,
        penalty["query_terms_any"],
    ):
        return False
    if penalty.get("query_terms_not") and _matched_terms(query, penalty["query_terms_not"]):
        return False
    if penalty.get("text_any") and not _matched_terms(text, penalty["text_any"]):
        return False
    if penalty.get("text_not") and _matched_terms(text, penalty["text_not"]):
        return False
    return True


def _matched_catalog_labels(text: str, catalog: dict[str, list[str]]) -> list[str]:
    """找出在文章文本中匹配到的词表键名（ticker/topic/event）。"""
    labels: list[str] = []
    for label, terms in catalog.items():
        if _catalog_label_matches(text, label, terms):
            labels.append(label)
    return labels


def _catalog_label_matches(text: str, label: str, terms: list[str]) -> bool:
    """
    检查单个词表标签是否匹配文章文本。

    短标签（≤2 字符，如股票 ticker）匹配 $AAPL、NYSE: AAPL、NASDAQ: AAPL
    等模式。长标签使用单词边界正则匹配。
    """
    raw_text = text
    lower_text = text.lower()
    for term in terms:
        if len(str(term).strip()) <= 2 and str(term).strip().upper() == label.upper():
            continue
        if _term_matches(lower_text, term):
            return True

    upper_label = label.upper()
    if len(upper_label) <= 2:
        return bool(re.search(rf"(\${upper_label}\b|\bNYSE:\s*{upper_label}\b|\bNASDAQ:\s*{upper_label}\b)", raw_text))
    return bool(re.search(rf"\b{re.escape(upper_label)}\b", raw_text))


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    """返回列表中有哪些词出现在（已小写的）文本中。"""
    lower_text = text.lower()
    hits = [term for term in terms if _term_matches(lower_text, str(term))]
    return _dedupe_lower(hits)


def _term_matches(lower_text: str, term: str) -> bool:
    """
    单词边界匹配单个词条。

    短词（≤2 个字符，纯字母）使用显式单词边界。
    包含非单词字符的词（如 "s&p"）使用普通子串匹配。
    其余词使用正则单词边界匹配。
    """
    normalized = str(term or "").strip().lower()
    if not normalized:
        return False
    if len(normalized) <= 2 and normalized.isalpha():
        return bool(re.search(rf"\b{re.escape(normalized)}\b", lower_text))
    if re.search(r"\W", normalized):
        return normalized in lower_text
    return bool(re.search(rf"\b{re.escape(normalized)}\b", lower_text))


def _query_hits(text: str, query_text: str) -> list[str]:
    """统计查询中的分词在文章文本中出现的数量（已过滤停用词）。"""
    text_tokens = set(_tokenize(text))
    hits: list[str] = []
    for token in _tokenize(query_text):
        if token in STOP_WORDS:
            continue
        if token in text_tokens:
            hits.append(token)
    return _dedupe_lower(hits)


def _tokenize(text: str) -> list[str]:
    """从文本中提取字母数字词条（≥2 字符），并过滤停用词。"""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9&.+-]*", (text or "").lower())
    return [token for token in tokens if len(token) >= 2 and token not in STOP_WORDS]


def _has_market_or_query_signal(text: str, query: str, rules: dict[str, Any]) -> bool:
    """
    检查文章是否仍具有市场相关性信号，用于抵消命中的负向词。
    由 _passes_hard_filter 调用，避免丢弃提及负向词但仍属于
    市场/ticker/topic/event 范畴的文章。
    """
    if _matched_terms(text, rules.get("market_terms", [])):
        return True
    if _matched_catalog_labels(text, rules.get("tickers", {})):
        return True
    if _matched_catalog_labels(text, rules.get("topics", {})):
        return True
    if _matched_catalog_labels(text, rules.get("events", {})):
        return True
    return bool(_query_hits(text, query))


def _item_text(item: NewsItem) -> str:
    """将条目所有可搜索的文本字段拼接为一个字符串，用于关键词匹配。"""
    return " ".join(
        part
        for part in (
            item.title,
            item.title_zh,
            item.content,
            item.content_zh,
            item.source,
            item.url,
        )
        if part
    )


def _news_key(item: NewsItem) -> str:
    """
    新闻条目的稳定去重键：优先使用归一化后的 URL（去除 fragment），
    若 URL 不存在则回退到归一化标题。用于硬过滤去重和按意图召回。
    """
    url = (item.url or "").strip().lower()
    if url:
        return "url:" + re.sub(r"#.*$", "", url).rstrip("/")
    title = re.sub(r"\W+", " ", (item.title or "").strip().lower())
    return "title:" + " ".join(title.split())


def _published_timestamp(item: NewsItem) -> float:
    """返回 UTC 时间戳用于排序；无法解析时返回 0.0（排到最末）。"""
    published = parse_news_time(item.published_at)
    return published.timestamp() if published else 0.0


def _normalize_source(source: str | None, url: str | None) -> str:
    """
    归一化来源字段用于多样性计数。
    若 source 为空，则回退为从 URL 提取域名。
    """
    source_text = (source or "").strip().lower()
    if source_text:
        return source_text
    url_text = (url or "").strip().lower()
    match = re.match(r"^https?://([^/]+)", url_text)
    return match.group(1).removeprefix("www.") if match else url_text


def _dedupe_upper(items: list[str]) -> list[str]:
    """列表去重（不区分大小写，输出大写）。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item or "").strip().upper()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _dedupe_lower(items: list[str]) -> list[str]:
    """列表去重（不区分大小写，输出小写）。"""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item or "").strip().lower()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _compact_reasons(reasons: list[str], limit: int = 12) -> list[str]:
    """去重并裁剪评分原因列表到指定最大长度，用于展示。"""
    seen: set[str] = set()
    result: list[str] = []
    for reason in reasons:
        if reason and reason not in seen:
            seen.add(reason)
            result.append(reason)
        if len(result) >= limit:
            break
    return result
