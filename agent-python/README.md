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
│       ├── reports.py
│       ├── watchlists.py
│       ├── report_jobs.py
│       └── auth.py
├── auth/
│   ├── dependencies.py
│   ├── repository.py
│   ├── schemas.py
│   ├── security.py
│   └── service.py
├── watchlists/
│   └── service.py
├── report_jobs/
│   ├── repository.py
│   ├── scheduler.py
│   ├── schemas.py
│   ├── service.py
│   └── worker.py
├── reports/
│   ├── repository.py
│   ├── schemas.py
│   └── service.py
├── market_pulse/
│   ├── graph.py
│   ├── state.py
│   ├── service.py
│   ├── nodes/
│   ├── analyzers/
│   ├── filters/
│   │   └── news_filter.py
│   ├── rankers/
│   │   ├── news_ranker.py
│   │   └── source_weight.py
│   ├── utils/
│   │   └── news_normalizer.py
│   ├── workflows/
│   ├── schemas.py
│   └── repository.py
├── clients/
├── storage/
│   ├── report_store.py
│   └── watchlist_store.py
├── safety/
├── scripts/
│   ├── smoke_test.py
│   ├── verify_closed_loop.py
│   ├── check_news_quality.py
│   └── check_rss_sources.py
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

不依赖 Celery / Redis / Kafka，纯 SQLite + asyncio。

## Ranker 质量评估

ranker 排序质量通过小型离线标注集评估，不接入线上流程。

### 数据集

文件：`evals/ranker_eval_dataset.jsonl`，每行一条 JSON 标注样本：

```json
{
  "query": "NVIDIA AI chips",
  "title": "Nvidia announces new AI chip platform",
  "description": "...",
  "source_name": "Reuters",
  "url": "https://example.com/news/1",
  "published_at": "2026-05-20T10:00:00Z",
  "label": "important"
}
```

**label 含义：**

| label | 含义 |
|-------|------|
| `important` | 与 query 高度相关，对市场有直接影响 |
| `related` | 与 query 相关，值得关注 |
| `weakly_related` | 弱相关，不在 top 也不影响评估指标 |
| `irrelevant` | 不相关，应该被 ranker 过滤 |

覆盖 5 个 query，数据集已扩充到 56+ 条（每个 query 11-12 条），刻意包含边界 case（关键词歧义、权威来源弱相关、未知来源强相关等）。

### 评估指标

- **Precision@5 / @10**：top 5/10 中 label 为 `important` 或 `related` 的比例
- **Important Recall@10**：全部 `important` 样本有多少出现在 top 10
- **Irrelevant Rate@10**：top 10 中 `irrelevant` 的比例

### 运行方式

```powershell
cd agent-python
python evals/ranker_eval.py
```

### Ranker 排序逻辑

ranker 综合以下信号排序：

1. **正向关键词**：ticker 匹配 (+4)、event 匹配 (+3)、topic 匹配 (+2)、market terms 匹配 (+1 each)
2. **query-aware boost**：根据 query 类型（earnings/macro/commodity/tech_ai）加权领域专属词 (+2 each)
3. **source_weight**：source_weight * 5 加入总分，Unknown source 且无强信号时额外降权 -2
4. **freshness_score**：6h 内 +3、24h 内 +2、72h 内 +1、缺失 -> -1.5
5. **负向降权**：
   - strong negative（sports、movie、celebrity、recipe、cooking、pet 等）：-5
   - weak negative（store opening、flagship store、coupon、blog opinion 等）：-2
   - query-aware negative（如 Apple earnings 中 store/retail 词）：-3
6. **query 匹配**：token 命中加分，忽略 stop words

每条 ranked news 保留 `relevance_score`、`source_weight`、`freshness_score`、`negative_score`、`relevance_reasons`、`negative_reasons` 用于可解释性。

eval 输出三份报告：
- 终端：per-query 指标 + top ranked 详情 + warnings
- `evals/ranker_eval_report.json`：结构化 JSON 报告，含所有得分和 reasons
- `evals/ranker_eval_summary.csv`：CSV 简表，可直接导入 Excel/Google Sheets

false positives 和 missed important 可用于反向优化 ranker 规则。

### 说明

当前只是小型离线评估脚本（56+ 条样本），用于量化 ranker 排序效果。rank 不代表投资预测能力。不引入机器学习框架或向量库。

## 安全合规 Guard

系统自动扫描报告内容，禁止输出投资建议、收益承诺或交易指令，并为每个报告附加免责声明。

### 禁止表达

中英文强制匹配，命中即标记 `unsafe`：

| 中文 | 英文 |
|------|------|
| 建议买入 / 建议卖出 | buy recommendation / sell recommendation |
| 强烈推荐买入 / 必须买入 | must buy / strong buy |
| 必涨 / 稳赚 / 保证收益 | guaranteed return |
| 无风险 / 目标价一定达到 | risk-free |
| 马上入场 / 抄底 / 梭哈 / 满仓 | - |

### compliance_status 含义

| status | 含义 |
|--------|------|
| `safe` | 未检测到违规表达 |
| `warning` | guard 扫描失败或仅轻微风险（默认追加 disclaimer） |
| `unsafe` | 检测到明确的投资建议或收益承诺，前端应高亮提示 |

### 免责声明

每个报告自动附带固定免责声明：

> 本报告由 AI 基于公开新闻信息生成，仅用于信息整理、研究参考和风险提示，不构成任何投资建议、买卖建议或收益承诺。投资有风险，用户应自行判断并承担决策责任。

### API 响应

`GET /api/reports/{id}` 返回：
- `report.compliance_status`：当前合规状态
- `disclaimer`：免责声明全文

### 测试脚本

```powershell
python scripts/check_report_guard.py
```

## 前端 (Frontend)

前端为纯 HTML/JS SPA，无构建步骤，直接打开 `frontend/index.html` 或用任意 HTTP 服务器托管。

### 启动方式

```powershell
# 方式 1：直接用浏览器打开
start frontend/index.html

# 方式 2：用 Python 简单 HTTP 服务器托管
cd frontend
python -m http.server 3000
# 然后访问 http://127.0.0.1:3000
```

### 使用流程

1. 启动后端：`uvicorn app.main:app --host 127.0.0.1 --port 8010`
2. 打开前端页面
3. 注册账号 → 登录
4. 创建 Watchlist → 添加 item（ticker/topic/macro/commodity/custom）
5. 创建 Report Job → 手动 Run Job
6. 查看 Reports 列表 → 点击查看详情（含 compliance_status 和 disclaimer）

### 页面路由

| Hash | 页面 |
|------|------|
| `#login` | 登录页 |
| `#register` | 注册页 |
| `#watchlists` | Watchlist 管理（创建、查看列表） |
| `#watchlist-detail/{id}` | Watchlist 详情（添加 item、创建 job） |
| `#reports` | 报告列表（含 compliance_status） |
| `#report-detail/{id}` | 报告详情（disclaimer、source items） |
| `#jobs` | 报告任务列表（状态、手动 Run） |

### 技术栈

- 纯 HTML + CSS + Vanilla JavaScript（无框架）
- Hash-based SPA routing
- JWT token 存储在 localStorage
- 后端 API 地址默认 `http://127.0.0.1:8010`（可通过页面手动修改）
