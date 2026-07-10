# Financial Agents

## 项目定位

Financial Agents 是一个财经新闻脉冲分析 Agent：抓取财经新闻，筛选高影响事件，调用 LLM 做结构化分析，输出可评测、可追踪、可解释的市场简报。

本项目不做真实交易，不接券商 API，不生成自动下单、买卖建议、目标价建议或投资组合建议。所有报告仅用于公开信息整理、市场研究和工程演示，不构成投资建议。

## 核心功能

- **多源财经新闻抓取**：Marketaux（可选）/ 财经 RSS / 公司与市场 feed（CNBC、MarketWatch、NASDAQ、Seeking Alpha、Yahoo、WSJ）
- **三层级联排序**：粗筛（正则）→ 语义精排（embedding）→ LLM 终选（多样性约束），从 ~300 条候选收敛到 ~8 条
- **LLM 结构化分析**：统一通过 DeepSeek/OpenAI 兼容接口调用，每条新闻 2 次 LLM（实体+事件+风险 / 报告生成）
- **Agent 编排**：LangGraph 6 节点主流程（collect → rank → analyze → risk_route → risk_review → generate_report）
- **Trace 可观测性**：节点级耗时/错误记录 + 外部 API 调用次数统计（Marketaux、Alpha Vantage），前端瀑布图展示
- **Eval 评测**：119 条离线数据集，Precision@5=0.96，ImportantRecall@10=1.00
- **前端功能**：登录、watchlist（预设 + 自定义 + 一键组合包）、报告任务、报告历史和详情

## 唯一后端入口

```text
agent-python/app/main.py
```

启动后端：

```powershell
cd "D:\desk top\financial-agents\agent-python"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

启动前端：

```powershell
cd "D:\desk top\financial-agents\frontend"
python -m http.server 5173
```

打开：

```text
http://127.0.0.1:5173
```

API 文档：

```text
http://127.0.0.1:8010/docs
```

## Agent 工作流

推荐 demo 入口：

```text
POST /api/agent/market-pulse/langgraph
```

LangGraph 主流程（6 节点 + 条件分支）：

```text
START
  → collect_news     # 多源收集（~300 条候选池）
  → rank_news        # 三层排序（300→60→40→8）
  → analyze_items    # 并发 LLM 分析（每条 2 次调用）
  → risk_route       # 条件路由
  → risk_review      # 高风险 → 附加审查节点
  → generate_report  # 趋势 + 信号 + 综合总结 + 合规 + 落库
  → END
```

### 排序管道（三层级联）

```
candidate_news (300条)
  │
  ▼ Layer 1: coarse_filter (纯正则, <50ms, 同步)
  │   300 → 60
  │   从 query 提取关键词 → 覆盖率打分 → 每意图强制召回 ≥5条
  │
  ▼ Layer 2: embedding_rerank (调 embedding API, 异步)
  │   60 → 40
  │   query 向量 vs 标题+摘要向量 → 余弦相似度排序
  │
  ▼ Layer 3: llm_rerank (一次 LLM 调用, 异步)
  │   40 → 8
  │   15 条打包成 prompt → LLM 通读后选 top 8，要求覆盖所有 topic
  │
  ▼ selected_news → analyze_items
```

### 单条新闻分析链（5 步，2 次 LLM 调用）

```
输入: title + content + source + published_at

步骤1 ─ LLM ─→ entity + event + risk (合并为一次调用)
步骤2 ─ 规则 ─→ 公司→ticker + topic→ETF + 板块关联 (90+ SECTOR_PEERS)
步骤3 ─ API ─→ Alpha Vantage 行情 (请求级缓存 + 失败追踪)
步骤4 ─ LLM ─→ 中文五段式报告
步骤5 ─ 规则 ─→ 合规扫描 + 免责声明
```

## 系统架构

```text
agent-python/
  app/
    main.py                  # FastAPI 唯一入口
    config.py                # 配置加载 (DeepSeek/OpenAI 自动 fallback)
    errors.py                # 统一错误类型
    schemas.py               # 工程化 Agent 数据模型
    api/                     # REST API 路由
      auth.py                #   注册/登录
      health.py              #   健康检查
      market_pulse.py         #   Agent 执行入口 (LangGraph + legacy)
      opportunities.py        #   机会扫描
      reports.py              #   报告 CRUD + trace
      report_jobs.py          #   报告任务生命周期
      watchlists.py           #   关注列表 CRUD
    agents/                  # 轻量可测试 workflow (工程演示用)
    services/                # news / llm / ranking 服务封装
    core/                    # trace / logging / config
    eval/                    # 离线 ranking 评测
  market_pulse/
    graph.py                 # LangGraph 编排器
    state.py                 # 图状态 TypedDict
    schemas.py               # 产品数据模型 (21+ Pydantic models)
    service.py               # 编排门面 (legacy + LangGraph + opportunity scan)
    trace.py                 # 节点装饰器 + trace 落盘
    api_metrics.py           # 按请求隔离的 API 调用计数器 (contextvars)
    nodes/                   # 6 个 LangGraph 节点
    rankers/                 # 三层排序 (coarse / embedding / llm) + source_weight
    analyzers/               # 实体/事件/风险解析、行情缓存、报告生成、ticker 关联
    workflows/               # 单条新闻分析 workflow
    filters/                 # 去重 + 新鲜度过滤
    repository.py            # 报告持久化门面
  clients/                   # 外部 API 客户端
    llm_client.py            #   OpenAI 兼容 chat completion (含重试)
    marketaux_client.py      #   Marketaux 新闻搜索
    rss_client.py            #   公司与市场 RSS 聚合
    fin_news_rss.py          #   多源财经 RSS (CNBC/MarketWatch/...)
    alpha_vantage_client.py  #   行情数据 (TIME_SERIES_DAILY)
    retry.py                 #   HTTP 重试工具
  report_jobs/               # 报告任务系统
    scheduler.py             #   每日定时任务
    worker.py                #   后台 worker (信号处理)
    service.py               #   任务编排
    repository.py            #   SQLite CRUD + 乐观锁
    trace_repository.py      #   步骤级 trace 落库
  reports/                   # 报告服务 + 合规守卫
  watchlists/                # 关注列表查询构建
  auth/                      # JWT + bcrypt 鉴权
  storage/                   # SQLite 数据库 (8 张表 + 迁移 + 索引)
  safety/                    # 输出合规 (禁用词扫描 + 免责声明注入)
  config/                    # 配置文件
    company_feeds.json       #   公司 RSS feed 与搜索查询
    market_feeds.json        #   市场 RSS feed 分组
    ranker_rules.json        #   旧版排名权重 (legacy path 保留)
  scripts/                   # 运维脚本 (check_config, smoke_test, ...)
  evals/                     # 评测脚本 + 数据集
frontend/                    # 静态 SPA 前端
tests/                       # pytest 测试 (46 个用例)
```

## 数据模型

**产品数据模型**（`agent-python/market_pulse/schemas.py`，21+ Pydantic models）：

| 模型 | 用途 |
|------|------|
| `NewsItem` | 标准化新闻条目（含排序元数据：relevance_score, matched_tickers, source_weight, freshness_score） |
| `AnalyzeRequest` | 单条新闻分析输入 |
| `EntityResult` / `EventResult` / `RiskResult` | LLM 结构化提取结果 |
| `TickerLinks` / `MarketMetrics` | 股票关联 + 行情数据 |
| `WorkflowResult` | 单条新闻完整分析结果 |
| `DailyNewsAnalysis` | 新闻 + 分析结果的包装 |
| `TickerTrend` | 逐 ticker 聚合趋势 |
| `MarketSignal` | 结构化市场观察信号（含证据链、不确定性说明） |
| `FinancialRecommendation` | Legacy 兼容，新前端使用 MarketSignal |
| `MarketPulseResponse` | 最终报告响应 |

**工程化数据模型**（`agent-python/app/schemas.py`）：`NewsItem`, `RankedNewsItem`, `MarketSignal`, `AgentState`, `AnalysisReport`, `EvalCase`, `EvalResult` —— 用于轻量 workflow 和面试讲解。

## 信息来源

### 新闻来源

- **Marketaux**：`MARKETAUX_BASE_URL=https://api.marketaux.com/v1/news/all`（默认关闭，付费额度才启用）
- **多源财经 RSS**：CNBC、MarketWatch、NASDAQ、Seeking Alpha、Yahoo Finance、WSJ
- **配置化 feed**：`config/company_feeds.json`（公司 RSS + Google News fallback）、`config/market_feeds.json`（市场源分组）

### 行情来源

- **Alpha Vantage** `TIME_SERIES_DAILY`：计算 1/3/7 日涨跌幅、成交量变化、相对 SPY 表现

```env
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query
ALPHA_VANTAGE_API_KEY=your_key
```

行情数据仅用于市场反应观察（如"1 日上涨确认""成交量放大"），不用于交易建议。

## 环境变量

后端读取：

```text
D:\desk top\financial-agents\.env
```

配置模板：

```text
D:\desk top\financial-agents\.env.example
```

首次使用：

```powershell
cd "D:\desk top\financial-agents"
copy .env.example .env
```

### LLM 配置

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

也支持 OpenAI 兼容接口：

```env
LLM_BASE_URL=https://api.openai.com/v1/chat/completions
LLM_API_KEY=your_key
LLM_MODEL=gpt-4o-mini
```

若未单独配置 LLM key，会自动复用 DeepSeek key。

### Embedding 配置（Layer 2 语义精排）

```env
EMBEDDING_API_KEY=your_key
EMBEDDING_BASE_URL=https://api.openai.com/v1/embeddings
EMBEDDING_MODEL=text-embedding-3-small
```

不配置则 Layer 2 自动回退为截断，不影响管道运行。

### 新闻与行情

```env
MARKETAUX_API_KEY=your_key
ALPHA_VANTAGE_API_KEY=your_key
```

### 采集与分析规模

```env
# rank 后送入逐条 LLM 分析的新闻上限
MARKET_PULSE_MAX_ANALYZE=50
# 逐条 LLM 分析并发数
MARKET_PULSE_ANALYSIS_CONCURRENCY=6
# 逐条分析超时（秒）
MARKET_PULSE_ANALYSIS_TIMEOUT_SECONDS=90
# 采集是否启用 Marketaux（默认关，规避免费档限流）
COLLECT_ENABLE_MARKETAUX=false
```

**说明**：采集默认以多源 RSS 为主（公司源 + 市场源，约 300 条候选）。Marketaux 免费档每次运行约 21 次查询，常把候选池拖垮并触发新鲜度硬过滤导致空报告。`rank_news` 三层会放宽各层限额，让最多 `MARKET_PULSE_MAX_ANALYZE` 条通过并交给 LLM 逐条分析。条数越大，LLM 与 Alpha Vantage 调用次数越多、耗时越长，均记录在 trace 和 `api_call_stats` 中。

不要提交 `.env` 或真实 API key。

### 检查配置

```powershell
cd "D:\desk top\financial-agents\agent-python"
python scripts/check_config.py
python scripts/check_marketaux.py --query "NVIDIA AI chips"
python scripts/check_alpha_vantage.py --symbol AAPL
```

## Trace 可观测性

### LangGraph 节点 trace

每个节点由 `trace_node` 装饰器包裹，记录：节点名、耗时、输入/输出数量、错误信息、跳过的步骤。trace 保存到 `traces/{trace_id}.json`。

### 报告任务 trace

报告任务路径（`/api/report-jobs/{id}/run`）将节点级耗时/错误写入数据库：

- `report_traces`：每次运行的总体记录（状态、总耗时）
- `report_trace_steps`：每节点步骤（step_name、duration_ms、error、metadata_json）
- `api_call_stats`：按次运行的外部 API 调用次数

区分两种粒度：

- `logical_calls`：高层客户端调用次数（一次 `search_marketaux_news` / `fetch_alpha_vantage_daily` 记 1 次）
- `http_attempts`：真实 HTTP 请求次数，含重试

API 调用计数器使用 `contextvars` 实现按请求隔离，并发管道互不干扰。

### 查询接口

```text
GET /api/reports/{report_id}/trace
GET /api/report-jobs/{job_id}/trace
```

返回 `{ trace, steps, api_calls }`。前端报告详情页在报告下方以耗时瀑布图展示每个节点耗时、标红失败节点，并列出各 provider 的调用次数。

## Eval 评测体系

### Ranking 评测

离线 eval 只评估 Layer 1（coarse_filter），不调用真实 LLM 或新闻 API：

```powershell
cd "D:\desk top\financial-agents\agent-python"
python evals/ranker_eval.py
```

**数据集**：`evals/ranker_eval_dataset.jsonl` — 119 条，9 组 query，含中文标题、自由文本、边缘 case（空标题/短内容）。干扰项包括 Telegram 骗局、加密货币 spam、菜谱、游戏、宠物。

**标注四档**：`important` / `related` / `weakly_related` / `irrelevant`

**当前指标**：

| 指标 | 数值 | 说明 |
|------|------|------|
| Precision@5 | 0.96 | 前 5 条质量 |
| Precision@10 | 0.70 | 长列表稳定性（受子串误匹配影响） |
| Important Recall@10 | 1.00 | 重要新闻不遗漏 |
| Irrelevant Rate@10 | 0.16 | 噪声率（待 Layer 2+3 消灭） |

**局限性**：仅测 Layer 1，Layer 2+3 需要 API 不在离线范围；119 条定位为回归测试，非大规模 benchmark。

### Agent 评测

```powershell
cd "D:\desk top\financial-agents\agent-python"
python evals/agent_eval.py
```

模拟 Agent 工具调用序列，验证 5 个场景（正常流程、空新闻降级、高风险触发审查等）。

## 快速开始

安装依赖：

```powershell
cd "D:\desk top\financial-agents"
python -m pip install -r requirements.txt
```

运行后端：

```powershell
cd "D:\desk top\financial-agents\agent-python"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

运行前端：

```powershell
cd "D:\desk top\financial-agents\frontend"
python -m http.server 5173
```

## API 示例

```powershell
curl -X POST http://127.0.0.1:8010/api/agent/market-pulse/langgraph ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Nvidia AI chips and Fed inflation risk\",\"max_items\":5,\"tickers\":[\"NVDA\",\"AAPL\"]}"
```

关注列表报告生成：

```powershell
curl -X POST http://127.0.0.1:8010/api/watchlists/1/reports/generate ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer <token>" ^
  -d "{\"max_items\":8}"
```

## 测试

```powershell
cd "D:\desk top\financial-agents"
pytest
```

46 个测试，默认不依赖真实 API key，不调用真实 LLM。

## CI/CD

GitHub Actions 位于 `.github/workflows/ci.yml`：

```bash
pip install -r requirements.txt
pip install pytest pytest-cov ruff
ruff check .
pytest --cov=app
```

## 面试讲解要点

- **边界清晰**：只做市场观察和风险观察，不做交易建议，不接券商 API
- **三层排序管道**：粗筛→语义→LLM，每层独立可替换，离线可评测 Layer 1
- **每意图强制召回**：防止多 ticker watchlist 退化为单一主题
- **合并 LLM 调用**：7 步 → 5 步，3 次 LLM → 2 次
- **结构化状态**：Pydantic 模型贯穿全链路（NewsItem → TickerTrend → MarketSignal）
- **Agent 编排**：LangGraph 6 节点 + 条件分支（风险路由）
- **Trace 可观测性**：节点级耗时追踪 + API 调用计数 + 前端瀑布图
- **Eval 评测**：119 条标注数据集，Precision@5=0.96
- **并发安全**：`contextvars` 隔离 API 计数，`asyncio.Lock` 保护行情缓存
- **Fail-soft**：每个新闻源、每条新闻分析的失败都不阻塞管道
- **CI 保障**：46 个测试 + ruff lint

> 完整的 10 分钟项目解说见 [`docs/interview-guide.md`](docs/interview-guide.md)。

## 当前边界与未来优化

**当前边界**：

- 不做真实交易，不构成投资建议，不接券商 API
- 不输出买入/卖出/持仓/目标价建议
- Layer 2+3 依赖外部 API，离线 eval 仅覆盖 Layer 1
- 行情数据仅用于"市场确认信号"，Alpha Vantage 免费档有频率限制

**未来优化**：

- 去重逻辑统一为一个模块（当前 4 个变体散落各处）
- Layer 2+3 离线 mock 评测
- RSS feed 并行抓取（`asyncio.gather` 替代串行 for 循环）
- LLM 输出增加 JSON schema 严格校验
- Trace 可视化页面增强
- 增加并发场景和权限隔离的测试
