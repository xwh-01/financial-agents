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

## LangGraph 节点职责

- `collect_news`: 根据用户 query 调用新闻 client 搜索新闻；没有 query 时采集最新市场新闻。
- `rank_news`: 调用 `market_pulse/rankers/news_ranker.py` 对候选新闻排序并截取分析集合。
- `analyze_items`: 对多条入选新闻执行实体识别、事件分析、ticker 关联、市场影响、风险检查、报告生成和合规检查。
- `risk_route`: 根据整体风险等级做条件路由。
- `risk_review`: 对高风险结果汇总额外风险原因和合规提醒。
- `generate_report`: 汇总趋势、关注建议和最终报告，并通过 repository 保存历史报告。

## 目录职责

- `app`: API 层，只负责 FastAPI app、router 注册、请求响应。
- `app/api`: FastAPI 路由层，包括健康检查、Market Pulse 和报告查询。
- `market_pulse`: Market Pulse 核心业务域。
- `market_pulse/graph.py`: LangGraph 主流程编排。
- `market_pulse/nodes`: LangGraph 节点。
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

“这是一个由 LangGraph 编排的财经新闻 Market Pulse Agent。`market_pulse/analyzers` 目录中的模块是分析能力模块，不是多个独立乱跑的 Agent；主流程统一由 `market_pulse/graph.py` 编排，并通过 `market_pulse/service.py` 暴露给 FastAPI。”
