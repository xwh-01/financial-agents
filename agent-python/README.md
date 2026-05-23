# Financial Agents Python Service

这是 Financial Agents 的 Python 服务。当前主链路是由 FastAPI 暴露接口、由 LangGraph 编排的财经新闻 Market Pulse Agent。

## Main Workflow

当前推荐主接口：

```http
POST /api/agent/market-pulse/langgraph
```

当前 LangGraph 主流程：

```text
User Query
  ↓
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

## Directory Structure

```text
agent-python/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── errors.py
│   └── api/
│       ├── health.py
│       ├── market_pulse.py
│       └── reports.py
├── market_pulse/
│   ├── graph.py
│   ├── state.py
│   ├── service.py
│   ├── nodes/
│   ├── analyzers/
│   ├── rankers/
│   ├── schemas.py
│   └── repository.py
├── clients/
├── storage/
├── safety/
└── docs/
```

## Layer Responsibilities

- `app`: API 层，只负责 FastAPI app、router 注册、请求响应。
- `app/api`: FastAPI 路由层，包括健康检查、Market Pulse 和报告查询。
- `market_pulse`: 核心业务域。
- `market_pulse/service.py`: 业务入口，API 层只调用这里。
- `market_pulse/graph.py`: LangGraph 主流程编排。
- `market_pulse/nodes`: LangGraph 节点。
- `market_pulse/analyzers`: 单条新闻分析能力模块，不是独立乱跑的多 Agent。
- `market_pulse/rankers`: 新闻排序策略。
- `clients`: 外部服务调用，包括 LLM、新闻、RSS、行情数据。
- `market_pulse/repository.py`: 业务持久化入口。
- `storage/report_store.py`: 底层 SQLite 存储实现。
- `safety/report_guard.py`: 报告安全与合规检查。

旧目录 `agents/`、`workflows/`、`tools/`、`schemas/` 不再作为当前结构使用。

## Data Sources

当前数据源链路：

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

- `company rss_feeds`: 公司级 RSS 源。
- Yahoo Finance ticker RSS: `https://finance.yahoo.com/rss/headline?s=<TICKER>`。
- NVIDIA official RSS: `https://nvidianews.nvidia.com/rss`。
- Google News RSS fallback: 当公司 RSS 拉取不足时，使用 `search_queries` 构造 fallback RSS。
- News API search endpoint: 用于通用新闻搜索。

RSS 验证脚本：

```powershell
.\.venv\Scripts\python.exe scripts\check_rss_sources.py
```

## Run

打开虚拟环境并运行程序：

```powershell
cd agent-python
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## Verify

```powershell
python -m compileall agent-python
```

启动后测试主接口：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/agent/market-pulse/langgraph" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"Nvidia AI chips","max_items":3}'
```
