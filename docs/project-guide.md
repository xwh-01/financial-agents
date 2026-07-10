# Financial Agents · 项目设计与使用说明

> 市场情报 Agent 工作流。抓取财经新闻 → 筛选高影响事件 → LLM 结构化分析 →
> 输出可评测、可追踪、可解释的市场简报。
>
> **边界**：只做市场观察、风险观察、证据整理与研究引用；不做交易、不接券商 API、
> 不输出买入/卖出/目标价/持仓建议。每份用户可见报告都强制带免责声明。

---

## 1. 快速开始

### 1.1 安装依赖（务必用项目 venv，含 feedparser）
```powershell
cd "D:\desk top\financial-agents"
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
> 根 `requirements.txt` 通过 `-r agent-python/requirements.txt` 引入全部依赖，
> 其中 `feedparser==6.0.12` 是主 RSS 采集的硬依赖。**若服务器进程缺 feedparser，
> RSS 会静默返回 0 条**（见第 12 节排查）。

### 1.2 配置
后端只读一个配置文件 `.env`（不存在就从 `.env.example` 复制）：
```powershell
copy .env.example .env
```
不要提交 `.env` 或真实 API key（已在 `.gitignore` 中）。

### 1.3 启动
```powershell
# 后端（在 agent-python 下，用 venv 的 uvicorn）
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
# 前端
cd frontend; python -m http.server 5173
```
- 前端：http://127.0.0.1:5173
- API 文档：http://127.0.0.1:8010/docs

### 1.4 冒烟测试
```powershell
curl -X POST http://127.0.0.1:8010/api/agent/market-pulse/langgraph ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Nvidia AI chips and Fed inflation risk\",\"max_items\":8,\"tickers\":[\"NVDA\",\"AAPL\"]}"
```

---

## 2. 系统架构

```
FastAPI (agent-python/app/main.py 唯一入口)
  ├ api/            路由层：auth / watchlists / report_jobs / reports / market_pulse / opportunities / health
  ├ service 层      业务编排
  ├ market_pulse/
  │   ├ graph.py    LangGraph 编排（推荐主路径）
  │   ├ nodes/      collect_news → rank_news → analyze_items → risk_route → risk_review → generate_report
  │   ├ rankers/    三层排序：query_driven(粗筛) / embedding / llm_reranker
  │   ├ analyzers/  实体事件、ticker 关联、行情、报告生成
  │   ├ trace.py    节点级 trace 装饰器
  │   └ api_metrics.py  外部 API 调用计数（本项目新增）
  ├ clients/        rss / fin_news_rss / marketaux / alpha_vantage / llm（均带重试）
  ├ report_jobs/    任务队列（状态机）+ 任务 trace
  ├ reports/        用户报告存储与查询
  ├ watchlists/     自选列表
  ├ safety/         合规守卫
  └ storage/        SQLite 持久化
frontend/           纯静态前端（vanilla JS）
tests/              pytest（默认离线 mock）
```

技术栈：FastAPI + Pydantic + LangGraph + SQLite。无外部数据库依赖，离线可测。

启动时集中做三件事（`app/main.py`）：校验安全配置 → `init_db()` 建表/迁移 → 启动每日报告调度协程。

---

## 3. 核心工作流（LangGraph 主流程）

推荐 demo 入口：`POST /api/agent/market-pulse/langgraph`
编排：`collect_news → rank_news → analyze_items → risk_route --(条件)--> risk_review → generate_report`

| 节点 | 职责 | 关键上限/行为 |
|---|---|---|
| collect_news | 多源采集 → 去重截断 | 候选池 ≤300；来源：公司 RSS + 市场 RSS（默认），Marketaux 可选（默认关） |
| rank_news | 三层排序 | 粗筛(硬过滤:标题/新鲜度<7天) → 向量重排 → LLM 重排；选出 ≤`MARKET_PULSE_MAX_ANALYZE`(默认 50) |
| analyze_items | 逐条并发分析 | 每条：LLM 抽实体/事件/风险 → 关联 ticker → Alpha 补行情 → 生成单条报告；单条失败降级不中断 |
| risk_route | 条件路由 | 整体风险为 high 才走 risk_review，否则直达 generate_report（跳过也记 trace） |
| risk_review | 高风险复核 | 汇总高风险原因与合规违规项 |
| generate_report | 聚合产出 | TickerTrend → MarketSignal → 全局 LLM 综述 → 合规改写 + 免责声明 → 落库 |

两条入口共用同一张图：
- **Demo 直连**：无状态，跑完直接返回 JSON（含 report_id / trace_id）。
- **报告任务**：watchlist → report_job 入队 → 后台 worker 认领 → 传 `report_job_id/report_trace_id` 跑图 → 写 DB trace + 用户归属报告。

---

## 4. 数据模型（内存态）

- **管道模型** `market_pulse/schemas.py`：`NewsItem`（含 relevance_score / matched_tickers / source_weight / freshness_score 等排序特征）→ `WorkflowResult`（entity/event/ticker/risk/market/compliance 逐段）→ `MarketSignal`（对外观察，带 evidence_summary / supporting_articles / compliance_violation）。
- **工程化模型** `app/schemas.py`：`NewsItem → RankedNewsItem → MarketSignal → AnalysisReport`（内置 disclaimer 默认值）；`AgentState` 强类型状态。
- **图状态** `market_pulse/state.py`：`MarketPulseGraphState(TypedDict, total=False)`，字段逐节点收敛：`candidate_news → ranked_news → selected_news → analyzed_news → result`，另含 `collect_stats`、`trace_id`、`report_job_id/report_trace_id`。

---

## 5. 数据库设计（SQLite）

连接统一开 `foreign_keys=ON` + `busy_timeout=5000` + `journal_mode=WAL`（读写不互斥，适配 worker+API 并发）。

| 表 | 职责 | 关键点 |
|---|---|---|
| users | 账号 | email 唯一，password_hash |
| watchlists / watchlist_items | 自选列表 | item 支持 ticker/keyword；`UNIQUE(watchlist_id, symbol)` |
| reports / report_items | 报告主表 + 明细 | 主表 `report_json` 存全量快照；明细拆行便于按 ticker 检索 |
| report_jobs | 任务队列 | 状态机 + 重试 + 锁 + 取消 + 进度字段 |
| report_traces / report_trace_steps | 执行轨迹 | 一次运行 + 每节点步骤（耗时/进出/错误/metadata） |
| api_call_stats | 外部 API 计数（新增） | 按 trace 记 provider 的 logical_calls / http_attempts |

工程化细节：
- **无脚本迁移**：`_ensure_*_columns` 用 `PRAGMA table_info` 探测缺列再 `ALTER TABLE`。
- **面向查询建索引**：如 `idx_report_jobs_pending_scan(status,scheduled_for,created_at,id)`、`idx_reports_user_watchlist_created`。
- **两条落库路径**：Demo 节点走 `save_market_pulse_report`（基础列，无 user/watchlist、无明细）；Watchlist 路径走 `save_watchlist_report`（全量元数据 + report_items，前端读这条）。

---

## 6. 报告任务系统（状态机）

状态：`pending → running → succeeded | failed | dead | cancelled`

| 状态 | 含义 |
|---|---|
| pending | 已入队待认领（创建与执行解耦） |
| running | 已认领执行中（并发互斥 + 超时检测 + 进度） |
| succeeded | 终态成功，带 report_id |
| failed | 可重试的临时失败（attempt_count < max_attempts） |
| dead | 重试用尽的死信，不再自动重试 |
| cancelled | 用户主动取消（非错误、不重试） |

机制：
- **原子认领**：`UPDATE ... WHERE status IN(pending,failed) AND NOT EXISTS(同 watchlist running)`，`rowcount==1` 才算抢到。
- **超时回收**：`requeue_stale_running_jobs` 把超过 `report_job_stale_seconds` 的 running 转回 failed/dead。
- **协作式取消**：running 时只置 `cancel_requested=1`，节点执行前检查再安全退出。
- **调度**：每日到点为所有 watchlist 建任务，`has_daily_job_today_for_watchlist` 幂等去重。

---

## 7. 可观测性

### 7.1 节点级 trace
`trace_node` 装饰器包裹每个图节点，自动记 `node_name / duration_ms / input_count / output_count / error`。双写：
- DB：`report_traces` + `report_trace_steps`（供 API/前端查询）
- 文件：`storage/langgraph_traces/{trace_id}.json`（脱离 DB 复盘）

### 7.2 外部 API 调用计数（api_call_stats）
每次 run 开头 `reset_api_metrics()`，客户端调用时计数：
- `logical_calls`：高层调用次数（1 次 search_marketaux_news / fetch_alpha_vantage_daily 记 1）
- `http_attempts`：真实 HTTP 次数（含重试）

### 7.3 采集来源计数（collect_stats）
collect_news 步骤 metadata 带 `marketaux / company_rss / market_rss / raw_candidate_count / candidate_pool`，候选异常偏少时一眼定位是哪个源挂了。

### 7.4 查询与展示
- `GET /api/reports/{id}/trace` 与 `GET /api/report-jobs/{id}/trace` 返回 `{trace, steps, api_calls}`。
- 前端报告详情页「执行追踪」以耗时瀑布图展示每步耗时、标红失败节点、显示各源计数与 API 调用次数。

---

## 8. 合规守卫

`generate_report` 落库前强制过 `apply_output_compliance_guard`：
1. 正则改写敏感表达（"建议买入"→"可作为研究观察对象" 等）；
2. 报告缺免责声明则补上；
3. 命中违规的 signal 升级风险等级、置 `signal_type=risk_observation` + `compliance_violation=True`。

把"不做投资建议"的边界在数据层强制落地，而非靠 prompt 自觉。

---

## 9. 数据来源

| 来源 | 用途 | 现状 |
|---|---|---|
| 多源 RSS（CNBC/MarketWatch/NASDAQ/SeekingAlpha/Yahoo/WSJ + 公司源） | 新闻主来源 | **默认主力**，一次可得约 300 候选 |
| Marketaux | 查询定向新闻 | **默认关闭**（免费档限流严重，每次约 21 次查询会拖垮候选池）；`COLLECT_ENABLE_MARKETAUX=true` 且有付费额度时可开 |
| Alpha Vantage `TIME_SERIES_DAILY` | 行情佐证 | 一次查一只票，取 1/3/7 日涨跌 + 量变 + vs SPY；免费档限流，失败即熔断显示"数据暂不可用" |
| LLM（DeepSeek/OpenAI 兼容） | 抽取/重排/报告 | 统一 `chat_completion`，带重试 |

---

## 10. API 参考

**Auth**
- `POST /api/auth/register` · `POST /api/auth/login` · `GET /api/auth/me`

**Watchlists**
- `GET /api/watchlists` · `POST /api/watchlists`
- `GET /api/watchlists/{id}/items` · `POST /api/watchlists/{id}/items`
- `POST /api/watchlists/{id}/report-jobs`（建报告任务）

**Report Jobs**
- `GET /api/report-jobs` · `GET /api/report-jobs/{id}`
- `POST /api/report-jobs/{id}/run | /cancel | /retry`
- `GET /api/report-jobs/{id}/trace`
- `POST /api/report-jobs/run-pending-once | /create-daily-once`

**Reports**
- `GET /api/reports`（支持 watchlist_id / ticker / date / limit 过滤）
- `GET /api/reports/today` · `GET /api/reports/{id}` · `GET /api/reports/{id}/items` · `GET /api/reports/{id}/trace`

**Market Pulse / Opportunities**
- `POST /api/agent/market-pulse/langgraph`（**推荐主入口**）
- `POST /api/opportunities/scan`（今日机会扫描，纯新鲜度优先，不走 LangGraph）
- 遗留：`/agent/analyze`、`/agent/search-news`、`/agent/batch-analyze-news`、`/agent/daily-brief`、`/agent/market-pulse`、`/api/market-pulse/agent-run`、`GET /api/agent-traces/{trace_id}`

---

## 11. 配置项清单（.env）

```env
# LLM（DeepSeek 示例）
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Marketaux（默认关，可选）
COLLECT_ENABLE_MARKETAUX=false
MARKETAUX_API_KEY=your_key
MARKETAUX_BASE_URL=https://api.marketaux.com/v1/news/all

# Alpha Vantage（行情，可选）
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query
ALPHA_VANTAGE_API_KEY=your_key

# 采集与分析规模
MARKET_PULSE_MAX_ANALYZE=50            # rank 后保留并逐条 LLM 分析的上限
MARKET_PULSE_ANALYSIS_CONCURRENCY=6     # 逐条分析并发数
MARKET_PULSE_ANALYSIS_TIMEOUT_SECONDS=90

# 任务调度
ENABLE_REPORT_SCHEDULER=false
DAILY_REPORT_HOUR=8
REPORT_JOB_STALE_SECONDS=1800

# Trace / 安全
TRACE_DIR=traces
JWT_SECRET=change_me
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
```

---

## 12. 常见问题排查

**「直接没有新闻 / 报告是空的」**
1. 看后端控制台是否刷 `[fin-rss] feedparser is not installed; skip RSS parsing` → 服务器进程缺 feedparser：用 venv 启动或 `pip install -r requirements.txt`。
2. 查报告 trace 的 collect_news 步 `collect_stats`：
   - `company_rss=0 且 market_rss=0` → RSS 环境/网络问题（多为 feedparser 缺失或 IP 被 feed 限流）。
   - `marketaux=0` 属正常（默认关）。
3. 查 rank_news 步：若 `ranked_news_count=0` 而候选非 0 → 候选多为过期新闻，被新鲜度硬过滤清空（换新鲜数据源即可）。

**「行情全是 数据暂不可用」**
- Alpha 未配 key，或免费档限流（25/天），或 ticker 被 LLM 误解析。用 `python scripts/check_alpha_vantage.py --symbol AAPL` 验证连通。

**「诊断脚本」**
```powershell
python scripts/check_config.py
python scripts/check_marketaux.py --query "NVIDIA"
python scripts/check_alpha_vantage.py --symbol AAPL
```

---

## 13. 评测与 CI

- 离线 eval：`python -m app.eval.runner`，只评 ranking 质量（Precision@5/10、ImportantRecall@10、IrrelevantRate@10），不调真实 API。
- CI（`.github/workflows/ci.yml`）：`ruff check .` + `pytest --cov=app`。
- 测试默认离线 mock（conftest 里 mock 掉 feedparser、用临时 SQLite）。

---

## 14. 已知限制与未来方向

**已知限制**
- 无断点续跑：图未挂 checkpointer，重试整条重跑。
- API 计数是模块级、单 run 隔离，并发多 run 会互相污染（同 market_analyzer 缓存的既有限制）。
- Alpha/Marketaux 免费档限流，行情覆盖有限。
- ticker 解析依赖 LLM，偶有误解析。

**未来方向**
- 稳定行情源（缓存层 / 付费 / 备用源）与 ticker 解析修复。
- 把新鲜度/相关性调参纳入 eval 闭环。
- trace 可视化增强、Alpha 行情柱状图。
- 图挂 checkpointer 支持断点续跑；collect 全失败降级为占位而非中止。
- 轻量 workflow 与主 LangGraph 收敛，LLM 输出更严格 JSON schema 校验。

---

*本文档仅用于工程说明与研究演示。系统输出为市场观察与风险观察，不构成任何投资建议。*
