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

## 新闻质量控制

Market Pulse 在采集新闻后自动进行质量过滤，确保输入 LangGraph 的新闻更干净、更相关。

### URL 去重与标题归一化

```text
原始新闻池
  ↓
normalize_title (转小写、去标点、去多余空格)
normalize_url   (去除 utm_source/utm_medium 等追踪参数)
  ↓
dedupe_news
```

去重规则（优先级从高到低）：
1. normalized_url 相同 → 去重
2. normalized_title 相同 → 去重
3. content_hash (title + url SHA256) 相同 → 去重

冲突时择优：`source_weight` 高的保留；权重相同时保留发布时间更新的；时间也相同时保留先出现的。

### freshness 过滤

`filter_fresh_news(news_items, max_age_hours=72)`:
- 能解析 `published_at` 的新闻：超过 `max_age_hours` 的丢弃
- 兼容 `published_at` / `publishedAt` / `date` 等字段
- 缺少时间戳的新闻：不丢弃，但 ranker 会降权（`freshness_score = -1.5`）

### source_weight 加权

`get_source_weight(source_name, url)` 根据来源加权到 ranker 总分中：

| 来源 | 权重 |
|------|------|
| Reuters | 1.0 |
| Bloomberg | 1.0 |
| CNBC | 0.9 |
| Yahoo Finance | 0.85 |
| MarketWatch | 0.8 |
| Google News | 0.75 |
| Company IR/Newsroom | 0.95 |
| Unknown | 0.5 |

- 大小写不敏感
- 如果 source_name 为空，根据 URL 域名判断
- 未知来源不直接删除，只降权 (`score += source_weight * 5`)

### Ranker 综合评分

每条新闻的 `relevance_score` 由以下组成：
- ticker/event/topic 关键词匹配
- freshness 新鲜度加分（6h内 +3，24h内 +2，72h内 +1）
- source_weight 加权（`source_weight * 5`）
- query 关键词匹配

每条 ranked news 都会附加 `relevance_score`、`source_weight`、`freshness_score` 字段。

### 验证脚本

```powershell
python scripts/check_news_quality.py
```

输出：normalize_title/normalize_url 正确性、source_weight 查表、dedupe 去重结果、freshness 过滤结果、综合评分模拟。

## P0 产品闭环验证

跑通 auth -> watchlist -> report_job -> report 完整链路。

### Smoke Test Script

```powershell
# 启动服务 (默认端口 8010，scheduler 默认关闭)
cd agent-python
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010

# 如需开启每日定时任务，在 .env 中设置：
#   ENABLE_REPORT_SCHEDULER=true
# Scheduler 默认关闭 (ENABLE_REPORT_SCHEDULER=false)

# 另开终端运行冒烟测试
$env:BASE_URL = "http://127.0.0.1:8010"
python scripts/smoke_test.py
```

### PowerShell 逐步骤验证

**register**:

```powershell
$registerBody = @{
  email = "demo@example.com"
  password = "demo1234"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/auth/register" `
  -Method Post `
  -ContentType "application/json" `
  -Body $registerBody
```

**login**:

```powershell
$loginBody = @{
  email = "demo@example.com"
  password = "demo1234"
} | ConvertTo-Json

$login = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/auth/login" `
  -Method Post `
  -ContentType "application/json" `
  -Body $loginBody

$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }
```

**GET /api/auth/me**:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/auth/me" `
  -Method Get `
  -Headers $headers
```

**create watchlist**:

```powershell
$wl = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body '{"name":"P0 Verify Watchlist"}'
```

**add ticker item**:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($wl.id)/items" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body '{"item_type":"ticker","symbol":"NVDA","name":"NVIDIA","keyword":"NVIDIA"}'
```

**add topic item**:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($wl.id)/items" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body '{"item_type":"topic","keyword":"AI chips","display_name":"AI Chips"}'
```

**add macro item**:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($wl.id)/items" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body '{"item_type":"macro","keyword":"Fed interest rate","display_name":"Fed Interest Rate"}'
```

**add commodity item**:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($wl.id)/items" `
  -Method Post `
  -ContentType "application/json" `
  -Headers $headers `
  -Body '{"item_type":"commodity","keyword":"gold","display_name":"Gold"}'
```

**create report job**:

```powershell
$job = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($wl.id)/report-jobs" `
  -Method Post `
  -Headers $headers
```

**run report job**:

```powershell
$job = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/report-jobs/$($job.id)/run" `
  -Method Post `
  -Headers $headers
```

**get report job status**:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/report-jobs/$($job.id)" `
  -Method Get `
  -Headers $headers
```

**get report**:

```powershell
if ($job.report_id) {
    Invoke-RestMethod `
      -Uri "http://127.0.0.1:8010/api/reports/$($job.report_id)" `
      -Method Get `
      -Headers $headers

    Invoke-RestMethod `
      -Uri "http://127.0.0.1:8010/api/reports/$($job.report_id)/items" `
      -Method Get `
      -Headers $headers
}
```

**run smoke_test.py**:

```powershell
$env:BASE_URL = "http://127.0.0.1:8010"
python scripts/smoke_test.py

# 只创建 job，不手动运行（由 worker 处理）：
python scripts/smoke_test.py --skip-run-job
```

## 自动报告任务与 Worker

系统支持三种模式运行 report job：

### 1. 手动模式 (Manual)

通过 API 手动创建和运行 job，适合本地调试：

```powershell
# 创建 job
$job = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/watchlists/$($wl.id)/report-jobs" `
  -Method Post -Headers $headers

# 手动 run
$job = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/report-jobs/$($job.id)/run" `
  -Method Post -Headers $headers

# 查询状态
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/report-jobs/$($job.id)" `
  -Method Get -Headers $headers

# 触发一次扫描 (开发调试)
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/report-jobs/run-pending-once" `
  -Method Post -Headers $headers
```

### 2. Worker 模式 (Standalone Worker)

一个终端运行 FastAPI，另一个终端运行 worker：

```powershell
# 终端 1: 启动 API
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010

# 终端 2: 启动 worker
.\.venv\Scripts\activate
python -m report_jobs.worker
```

Worker 环境变量：

```env
REPORT_JOB_SCAN_INTERVAL_SECONDS=5   # 扫描间隔，默认 5 秒
```

Worker 行为：
- 每 N 秒扫描 pending / failed 未超 max_attempts 的任务
- 逐条 claim (pending/failed → running)，执行，标记 succeeded/failed/dead
- 单条失败不会退出，继续处理下一条
- Ctrl+C 优雅退出

### 3. Scheduler 模式 (Daily Auto-Create)

Scheduler 在 FastAPI 进程内运行，每天定时为所有 watchlist 创建 daily job。

开启方式：

```powershell
$env:ENABLE_REPORT_SCHEDULER = "true"
$env:DAILY_REPORT_HOUR = "8"
$env:DAILY_REPORT_MINUTE = "0"

uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Scheduler 环境变量（默认值即默认关闭）：

```env
ENABLE_REPORT_SCHEDULER=false    # 默认关闭
DAILY_REPORT_HOUR=8              # 每天几点创建 daily job
DAILY_REPORT_MINUTE=0            # 分钟
```

Scheduler 行为：
- Scheduler 只负责每天定时创建 daily job（不执行 LangGraph）
- 同一 watchlist 当天已有 pending/running/succeeded 的 daily job 不再重复创建
- 创建的 job 由 Worker 进程负责执行

### 防重复执行机制

Job 状态机：`pending → running → succeeded / failed → dead`

- `claim_pending_job()` 原子更新：`WHERE status IN ('pending','failed')` → `SET status='running'`
- `succeeded` / `dead` 状态不可再次执行
- `running` 状态不可被其他 worker claim
- `find_pending_jobs()` 只返回 `pending` 或 `failed` 且 `attempt_count < max_attempts`
- 失败后 worker 不重新 claim 原 job，等下次扫描时由 `find_pending_jobs` 再次返回
- 超过 `max_attempts` 标记为 `dead`，不再执行

### 完整部署示例

```powershell
# .env 或环境变量
ENABLE_REPORT_SCHEDULER=true
DAILY_REPORT_HOUR=8
DAILY_REPORT_MINUTE=0
REPORT_JOB_SCAN_INTERVAL_SECONDS=5

# 终端 1: API + Scheduler
uvicorn app.main:app --host 127.0.0.1 --port 8010

# 终端 2: Worker
python -m report_jobs.worker
```

不依赖 Celery / Redis / Kafka，纯 SQLite + asyncio。<｜end▁of▁thinking｜>

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="todowrite">
<｜｜DSML｜｜parameter name="todos" string="false">[{"priority":"high","content":"Read and understand existing report_jobs worker, service, repository","status":"completed"},{"priority":"high","content":"Rewrite worker.py: run_pending_jobs_once + run_worker_loop + __main__","status":"completed"},{"priority":"high","content":"Refactor run_job to accept already-claimed (running) state from worker","status":"completed"},{"priority":"high","content":"Add has_daily_job_today_for_watchlist dedup in repository + service","status":"completed"},{"priority":"high","content":"Rewrite scheduler.py with improved daily job creation (no worker loop)","status":"completed"},{"priority":"high","content":"Update app/main.py for conditional scheduler startup","status":"completed"},{"priority":"medium","content":"Add optional POST /api/report-jobs/run-pending-once endpoint","status":"completed"},{"priority":"medium","content":"Update smoke_test.py with --skip-run-job flag","status":"completed"},{"priority":"medium","content":"Update README.md with worker/scheduler docs","status":"completed"},{"priority":"high","content":"Run compileall and fix errors","status":"in_progress"}]
