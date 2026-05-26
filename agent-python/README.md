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

## Auth And Watchlists

Production deployments must set `JWT_SECRET` in the environment. The service has
a local development fallback secret only so the app can run on a fresh machine.

Register a user:

```powershell
$registerBody = @{
  email = "alice@example.com"
  password = "password123"
  nickname = "Alice"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/auth/register" `
  -Method Post `
  -ContentType "application/json" `
  -Body $registerBody
```

Login and keep the bearer token:

```powershell
$loginBody = @{
  email = "alice@example.com"
  password = "password123"
} | ConvertTo-Json

$login = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/auth/login" `
  -Method Post `
  -ContentType "application/json" `
  -Body $loginBody

$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }
```

Get current user:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/auth/me" `
  -Method Get `
  -Headers $headers
```

Create a watchlist with Bearer token:

```powershell
$watchlistBody = @{ name = "AI Stocks" } | ConvertTo-Json

$watchlist = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body $watchlistBody
```

Add a watchlist item with Bearer token:

```powershell
$itemBody = @{
  symbol = "NVDA"
  name = "NVIDIA"
  note = "AI chips"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($watchlist.id)/items" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body $itemBody
```

Reports compatibility note: old manually generated reports can remain with
`user_id = NULL`. Watchlist-generated reports are saved with both `user_id` and
`watchlist_id`.

## User Reports And Report Items

Watchlist-generated Market Pulse reports are now bound to both the authenticated
user and the source watchlist:

- `reports.user_id` identifies the owner.
- `reports.watchlist_id` identifies the watchlist used to build the query.
- `reports.report_json` stores the complete Market Pulse result.
- `report_items` stores one row per analyzed news item so the UI can show source
  title, URL, published time, tickers, topics, relevance score, risk, and impact
  details without reparsing the full report payload.

Historical reports are preserved. If an older `reports` table is present, startup
adds missing columns with `ALTER TABLE` and keeps existing rows.

Generate a watchlist report with Bearer token:

```powershell
$generateBody = @{ max_items = 5 } | ConvertTo-Json

$report = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($watchlist.id)/reports/generate" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body $generateBody

$reportId = $report.report_id
```

Query current user's reports:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/reports" `
  -Method Get `
  -Headers $headers
```

Query reports for one watchlist:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/reports?watchlist_id=$($watchlist.id)" `
  -Method Get `
  -Headers $headers
```

Query report detail with source items:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/reports/$reportId" `
  -Method Get `
  -Headers $headers
```

Query only source item details:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/reports/$reportId/items" `
  -Method Get `
  -Headers $headers
```

## Report Jobs And Daily Scheduler

`report_jobs` lets the service generate Market Pulse reports asynchronously from
a user's watchlist. Jobs are stored in SQLite and do not require Celery, Redis,
or Kafka.

Job status flow:

- `pending`: created and waiting to run.
- `running`: claimed by the worker.
- `succeeded`: report was generated and `report_id` is stored.
- `failed`: attempt failed and can be retried while under `max_attempts`.
- `dead`: attempts reached `max_attempts`; the job will not be retried.

Scheduler settings:

```env
ENABLE_REPORT_SCHEDULER=false
DAILY_REPORT_HOUR=8
DAILY_REPORT_MINUTE=0
REPORT_JOB_SCAN_SECONDS=60
```

When `ENABLE_REPORT_SCHEDULER=true`, FastAPI startup launches lightweight
background tasks. One task creates daily jobs for all watchlists at the configured
time, and another scans pending jobs every `REPORT_JOB_SCAN_SECONDS`. Shutdown
cancels these tasks gracefully. If startup fails, the app logs a warning and
continues serving existing APIs.

Create a report job:

```powershell
$job = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($watchlist.id)/report-jobs" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body '{"job_type":"manual"}'
```

Manually run a job for local testing:

```powershell
$job = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/report-jobs/$($job.id)/run" `
  -Method Post `
  -Headers $headers
```

Check job status:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/report-jobs/$($job.id)" `
  -Method Get `
  -Headers $headers
```

List current user's jobs:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/report-jobs" `
  -Method Get `
  -Headers $headers
```

Fetch the generated report:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/reports/$($job.report_id)" `
  -Method Get `
  -Headers $headers
```
