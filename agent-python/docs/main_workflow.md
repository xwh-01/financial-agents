# 项目主链路 / Main Workflow

这是一个由 LangGraph 编排的财经新闻 Market Pulse Agent。`market_pulse/analyzers/` 中的模块是分析能力模块，不是多个独立乱跑的 Agent；主流程统一由 `market_pulse/graph.py` 编排，并通过 `market_pulse/service.py` 暴露给 FastAPI。

## 主链路

```text
FastAPI Route
  ↓
market_pulse/service.py
  ↓
market_pulse/graph.py
  ↓
collect_news
  ↓
rank_news
  ↓
analyze_items
  ↓
risk_route
  ├── high risk → risk_review
  └── normal    → generate_report
  ↓
repository 保存报告
  ↓
Return Report
```

主接口：

```http
POST /api/agent/market-pulse/langgraph
```

LangGraph 主入口：

```text
agent-python/market_pulse/graph.py
```

API 调用入口：

```text
agent-python/market_pulse/service.py
```

单条新闻分析流程入口：

```text
agent-python/market_pulse/workflows/single_news.py
```

## LangGraph 节点职责

- `collect_news`: 根据用户 query 调用新闻 client 搜索新闻；没有 query 时采集最新市场新闻。
- `rank_news`: 调用 `market_pulse/rankers/news_ranker.py` 对候选新闻排序并截取分析集合。
- `analyze_items`: 对多条入选新闻复用 `workflows/single_news.py` 执行单条新闻分析。
- `risk_route`: 根据整体风险等级做条件路由。
- `risk_review`: 对高风险结果汇总额外风险原因和合规提醒。
- `generate_report`: 汇总趋势、关注建议和最终报告，并通过 repository 保存历史报告。

## 单条新闻分析流程

```text
resolve_entities
  ↓
analyze_event
  ↓
link_tickers
  ↓
analyze_market
  ↓
check_risk
  ↓
generate_report
  ↓
check_compliance
```

## LLM 使用点

- `market_pulse/analyzers/entity_resolver.py`: 使用 LLM 识别公司、ticker、人物、主题。
- `market_pulse/analyzers/event_analyzer.py`: 使用 LLM 判断事件类型、情绪、影响强度、置信度。
- `market_pulse/analyzers/report_generator.py`: 使用 LLM 生成中文报告。
- 新闻采集、排序、风险规则、报告持久化不依赖 LLM。

## 新闻新鲜度控制

- `NewsItem` 同时保留 `published_at` 和 `fetched_at`。
- `published_at` 来自新闻 API 或 RSS 条目的发布时间；`fetched_at` 是系统采集到新闻时的 UTC ISO 时间。
- 采集后会基于 URL 和 title 去重，避免同一条新闻重复进入候选池。
- `market_pulse/rankers/news_ranker.py` 在排序前解析发布时间，执行时间窗口过滤和 freshness 加权。
- `published_at` 可解析且超过 7 天的新闻默认过滤，不优先进入 LLM 分析。
- `published_at` 缺失时不会直接丢弃，但会降低分数并加入 `freshness=missing_published_at`。
- 最近 6 小时新闻加分最高，最近 24 小时次之，最近 3 天再次之。

## 目录职责

- `app`: API 层，只负责 FastAPI app、router 注册、请求响应。
- `app/api`: FastAPI 路由层，包括健康检查、Market Pulse 和报告查询。
- `market_pulse`: Market Pulse 核心业务域。
- `market_pulse/graph.py`: LangGraph 主流程编排。
- `market_pulse/nodes`: LangGraph 节点。
- `market_pulse/workflows`: 可复用的业务流程，目前包含单条新闻分析流程。
- `market_pulse/analyzers`: 单条新闻分析能力。
- `market_pulse/rankers`: 排序策略。
- `clients`: 外部服务调用，包括 LLM、新闻、RSS、行情数据。
- `market_pulse/repository.py`: 业务持久化入口。
- `storage/report_store.py`: 底层 SQLite 存储实现。
- `safety/report_guard.py`: 报告合规与安全检查。

## 数据源链路

Market Pulse 当前数据源链路：

```text
company_feeds.json
  ↓
clients/rss_client.py
  ↓
collect_company_market_news
  ↓
market_pulse/service.py 或 market_pulse/nodes/collect_news.py
  ↓
ranker
  ↓
analyzer
  ↓
report
```

数据源包括：

- `company rss_feeds`: `agent-python/config/company_feeds.json` 中维护的公司 RSS。
- Yahoo Finance ticker RSS: `https://finance.yahoo.com/rss/headline?s=<TICKER>`。
- NVIDIA official RSS: `https://nvidianews.nvidia.com/rss`。
- Google News RSS fallback: 当公司 RSS 拉取不足时，使用 `search_queries` 构造 Google News RSS。
- News API search endpoint: 用于通用新闻搜索和候选新闻补充。

## 面试时推荐说法

“这是一个由 LangGraph 编排的财经新闻 Market Pulse Agent。`market_pulse/analyzers` 目录中的模块是分析能力模块，不是多个独立乱跑的 Agent；主流程统一由 `market_pulse/graph.py` 编排。单条新闻分析流程沉淀在 `market_pulse/workflows/single_news.py`，由 API service 和 LangGraph 节点共同复用。”

## Rank News Pipeline

`rank_news` is the deterministic top-layer selector before LLM analysis:

1. `collect_news` provides roughly 100-300 candidate articles.
2. `hard_filter` removes stale articles, empty titles, duplicates, and obvious low-quality noise.
3. The ranker parses the watchlist query into separate intents such as tickers, topics, macro, commodities, and custom notes.
4. Each intent recalls its own Top 20 candidates.
5. Recalled candidates are merged and deduplicated.
6. `hybrid_score` ranks by lexical query hits, ticker/topic/event matches, query profile boosts, source weight, freshness, and negative-context penalties.
7. `coverage selector` chooses the final Top 8-10 articles with ticker/topic/source diversity before `analyze_items`.

The ranker stays offline and explainable by default. Rules and weights live in `agent-python/config/ranker_rules.json`; the code path is `market_pulse/rankers/news_ranker.py`.
