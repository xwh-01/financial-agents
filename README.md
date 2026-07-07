# Financial Agents

## 项目定位

Financial Agents 是一个财经新闻脉冲分析 Agent：抓取财经新闻，筛选高影响事件，调用 LLM 做结构化分析，输出可评测、可追踪、可解释的市场简报。

本项目不做真实交易，不接券商 API，不生成自动下单、买卖建议、目标价建议或投资组合建议。所有报告仅用于公开信息整理、市场研究和工程演示，不构成投资建议。

## 核心功能

- 多源财经新闻抓取：Marketaux / NewsAPI / 财经 RSS / 公司与市场 feed
- 高影响新闻筛选：根据 ticker、事件类型、宏观词、风险词、来源权重和新鲜度排序
- LLM 结构化分析：统一通过 DeepSeek/OpenAI 兼容接口调用
- Agent 编排：推荐 demo 路径是 LangGraph Market Pulse
- Trace 可观测性：记录 Agent 节点执行过程、耗时、输入输出摘要和错误
- Eval 评测：离线评估 ranking 质量，不依赖真实 API key
- 前端功能：登录、watchlist、报告任务、报告历史和报告详情

## 唯一后端入口

本项目只保留一个完整后端入口：

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

现有 LangGraph 主流程：

```text
collect_news
-> rank_news
-> analyze_items
-> risk_route
-> risk_review
-> generate_report
```

工程化补充模块位于同一个后端包内：

```text
agent-python/app/agents/
agent-python/app/services/
agent-python/app/core/
agent-python/app/eval/
agent-python/app/schemas.py
```

这些模块用于面试讲解结构化状态、服务封装、轻量 workflow、trace 和 eval；完整产品运行仍然走 `agent-python/app/main.py`。

## 系统架构

```text
agent-python/
  app/
    main.py                  # FastAPI 唯一入口
    config.py                # 配置加载，兼容 DeepSeek / Marketaux
    schemas.py               # 工程化 Agent 数据模型
    api/                     # 前端与报告相关 API
    agents/                  # 轻量可测试 workflow
    services/                # news / llm / ranking 服务封装
    core/                    # trace / logging / config 兼容层
    eval/                    # 离线 ranking 评测
  market_pulse/
    graph.py                 # LangGraph Market Pulse 编排
    nodes/                   # collect/rank/analyze/risk/report 节点
    rankers/                 # 新闻排序逻辑
    analyzers/               # 事件、风险、报告生成
  clients/                   # LLM、新闻、RSS、市场数据客户端
  report_jobs/               # 报告任务与任务 trace
  reports/                   # 报告存储与查询
  watchlists/                # 自选列表
frontend/                    # 静态前端
tests/                       # pytest 测试
```

## 数据模型

工程化数据模型在 `agent-python/app/schemas.py`：

- `NewsItem`：标准化新闻输入
- `RankedNewsItem`：排序后的新闻，包含 `impact_score`、`reason`、`risk`、`confidence`
- `MarketSignal`：结构化市场观察
- `AgentState`：节点之间传递的状态，避免散乱 dict
- `AnalysisReport`：最终市场简报
- `EvalCase` / `EvalResult`：离线评测输入与结果

原有产品模型仍保留在 `agent-python/market_pulse/schemas.py`，用于现有 LangGraph 和前端兼容。

## 信息来源

新闻来源：

- Marketaux：`NEWS_BASE_URL=https://api.marketaux.com/v1/news/all`
- NewsAPI：通过 `NEWS_BASE_URL` 切换
- 财经 RSS：CNBC、MarketWatch、NASDAQ、Seeking Alpha、Yahoo、WSJ 等聚合逻辑
- 配置化 feed：
  - `agent-python/config/company_feeds.json`
  - `agent-python/config/market_feeds.json`

行情来源：

- Alpha Vantage，当前代码按 `TIME_SERIES_DAILY` 设计
- 配置：

```env
MARKET_BASE_URL=https://www.alphavantage.co/query
MARKET_API_KEY=your_key
```

行情数据只用于市场反应观察，例如 1/3/7 日涨跌幅和成交量变化，不用于交易建议。

## 环境变量

后端只读取一个配置文件：

```text
D:\desk top\financial-agents\.env
```

配置模板也只有一个：

```text
D:\desk top\financial-agents\.env.example
```

如果没有 `.env`，先复制：

```powershell
cd "D:\desk top\financial-agents"
copy .env.example .env
```

DeepSeek：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

Marketaux 新闻：

```env
NEWS_API_KEY=your_marketaux_key
NEWS_BASE_URL=https://api.marketaux.com/v1/news/all
```

也支持：

```env
MARKETAUX_API_KEY=your_marketaux_key
```

Alpha Vantage 行情，可选：

```env
MARKET_BASE_URL=https://www.alphavantage.co/query
MARKET_API_KEY=your_key
```

Trace：

```env
TRACE_DIR=traces
```

不要提交 `.env` 或真实 API key。

检查配置是否被读取：

```powershell
cd "D:\desk top\financial-agents\agent-python"
python scripts/check_config.py
```

## Trace 可观测性

LangGraph 主流程会记录节点级 trace。工程化轻量 workflow 会保存：

```text
traces/{trace_id}.json
```

trace 记录：

- `trace_id`
- `started_at` / `finished_at`
- `node_name`
- `input_summary`
- `output_summary`
- `latency_ms`
- `error`
- `llm_model`
- `token_usage`

面试时可以说明：项目不是黑盒 LLM 调用，而是有 Agent 执行轨迹，可以复盘每个节点。

## Eval 评测体系

离线 eval 只评估 ranking 质量，不调用真实 LLM，不调用真实新闻 API：

```powershell
cd "D:\desk top\financial-agents"
cd agent-python
python -m app.eval.runner
```

输出指标：

- `Precision@5`
- `Precision@10`
- `ImportantRecall@10`
- `IrrelevantRate@10`
- `average_latency_ms`

结果保存到：

```text
agent-python/app/eval/results/latest.json
```

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

## 运行示例

```powershell
curl -X POST http://127.0.0.1:8010/api/agent/market-pulse/langgraph ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"Nvidia AI chips and Fed inflation risk\",\"max_items\":5,\"tickers\":[\"NVDA\",\"AAPL\"]}"
```

## 验证行情接口

Alpha Vantage 的 `TIME_SERIES_DAILY` 配置：

```env
MARKET_BASE_URL=https://www.alphavantage.co/query
MARKET_API_KEY=your_key
```

验证配置是否读到：

```powershell
cd "D:\desk top\financial-agents\agent-python"
python scripts/check_config.py
```

验证 `TIME_SERIES_DAILY` 是否连通：

```powershell
python scripts/check_market_data.py --symbol AAPL
```

## 测试

```powershell
pytest
cd agent-python
python -m app.eval.runner
```

测试默认不依赖真实 API key，不调用真实 LLM。

## CI/CD

GitHub Actions 位于 `.github/workflows/ci.yml`：

```bash
pip install -r requirements.txt
pip install pytest pytest-cov ruff
ruff check .
pytest --cov=app
```

## 面试讲解重点

- 项目边界清晰：只做市场观察和风险观察，不做交易建议
- 结构化状态：用模型描述新闻、排序结果、市场信号和报告
- 工具/服务封装：新闻、LLM、排序、行情各自独立
- Agent 编排：LangGraph 主流程清晰
- Trace 可观测性：每次执行有节点轨迹
- Eval 质量评测：用离线指标衡量 ranking 效果
- CI 测试保障：配置、排序、trace、workflow、eval、报告任务都有测试

## 当前边界与未来优化

当前边界：

- 不做真实交易
- 不构成投资建议
- 不接券商 API
- 不输出买入、卖出、持仓或目标价建议

未来优化：

- 将工程化轻量 workflow 与现有 LangGraph 主流程进一步合并
- 增加 trace 可视化页面
- 增加更多离线 eval case
- 对 LLM 输出增加更严格的 JSON schema 校验
