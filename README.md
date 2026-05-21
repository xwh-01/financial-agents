# 财经时事影响分析 Agent / Financial Agents

## 项目简介

Financial Agents 是一个财经新闻研究参考项目。项目接入真实新闻源，根据财经时事、宏观事件、行业新闻和公司动态，分析新闻可能带来的市场影响，并输出趋势观察、风险提示和结构化报告。

本项目聚焦“研究参考”和“风险提示”，不做自动荐股，不承诺收益，也不构成投资建议。

## 核心流程

新闻采集 → 相关性排序 → 事件识别 → 市场影响分析 → 风险检查 → 报告生成 → 历史报告保存

## 项目主链路 / Main Workflow

当前推荐主接口是：

```http
POST /api/agent/market-pulse/langgraph
```

当前推荐主流程文件是：

```text
agent-python/market_pulse/graph.py
```

主链路如下：

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
save_report
  ↓
Return Report
```

当前代码已经收敛到最终目录结构：`app/` 是 API 层，`market_pulse/` 是核心业务域，`clients/` 负责真实外部服务访问，`storage/` 负责底层 SQLite 存储，`safety/` 负责合规检查。旧 `agents/`、`workflows/`、`tools/`、`schemas/` 目录已删除。

`market_pulse/analyzers/` 中的模块不是独立乱跑的多个 Agent，而是实体识别、事件分析、风险检查、报告生成等分析能力模块；这些能力由 `market_pulse/graph.py` 统一编排。

## 技术栈

- Python
- FastAPI
- Pydantic
- HTTPX
- LangGraph
- SQLite
- RSS / feedparser
- News API
- LLM API
- HTML
- JavaScript

## 目录结构

```text
.
├── agent-python/
│   ├── app/                 # FastAPI 应用入口、配置、错误和 API router
│   │   └── api/             # health、Market Pulse、reports 路由
│   ├── market_pulse/        # Market Pulse 业务域：service、graph、nodes、analyzers
│   ├── clients/             # LLM、新闻、RSS、市场数据等外部服务客户端
│   ├── config/              # 公司信息源配置
│   ├── data/                # SQLite 数据库文件，运行后自动生成
│   ├── storage/             # 历史报告持久化
│   ├── safety/              # 报告安全与合规检查
│   └── docs/                # 主链路说明
├── frontend/                # 简单前端页面
└── README.md
```

## 启动方式

```bash
cd agent-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后默认访问：

```text
http://127.0.0.1:8000
```

启动时会自动初始化 SQLite 数据库：

```text
agent-python/data/reports.db
```

## 接口示例

### 旧版 Market Pulse

```http
POST /agent/market-pulse
```

```json
{
  "limit": 50,
  "language": "en",
  "translate_to_zh": false,
  "max_items": 5
}
```

curl 示例：

```bash
curl -X POST http://127.0.0.1:8000/agent/market-pulse ^
  -H "Content-Type: application/json" ^
  -d "{\"limit\":50,\"language\":\"en\",\"translate_to_zh\":false,\"max_items\":5}"
```

### LangGraph Market Pulse

```http
POST /api/agent/market-pulse/langgraph
```

```json
{
  "query": "technology stocks and gold",
  "max_items": 5
}
```

该接口会执行 LangGraph 工作流，并将最终报告保存到 SQLite。返回结果中会包含 `report_id`。

### 查询历史报告

查询最近 20 条报告：

```http
GET /api/reports
```

查询单条报告详情：

```http
GET /api/reports/1
```

如果报告不存在，会返回 `404`。

## 公司维度信息源

Market Pulse 现在使用组合信息源补充公司相关新闻：

```text
News API 主路径 + 公司 RSS + Google News RSS fallback
```

第一版内置 5 个公司配置：

- NVIDIA / NVDA
- AMD / AMD
- Apple / AAPL
- Microsoft / MSFT
- Tesla / TSLA

配置文件位置：

```text
agent-python/config/company_feeds.json
```

配置示例：

```json
[
  {
    "company": "NVIDIA",
    "ticker": "NVDA",
    "rss_feeds": [],
    "search_queries": [
      "NVIDIA",
      "NVDA",
      "NVIDIA earnings",
      "NVIDIA AI chips"
    ]
  }
]
```

`rss_feeds` 可以后续补充公司官网或投资者关系 RSS；当公司 RSS 为空或失败时，系统会使用 Google News RSS 搜索型 fallback 补充相关新闻。单个 RSS 源失败会被跳过，不会中断整个 Market Pulse 流程。

相关环境变量：

```text
ENABLE_COMPANY_RSS=true
COMPANY_FEEDS_PATH=config/company_feeds.json
RSS_TIMEOUT_SECONDS=15
MIN_NEWS_COUNT=10
```

## LangGraph 工作流

```text
START
-> collect_news
-> rank_news
-> analyze_items
-> risk_route
   -> risk_review -> generate_report  # 整体风险等级为 high
   -> generate_report                 # 其他情况
-> save_report
-> END
```

节点说明：

- `collect_news`：复用真实新闻采集逻辑。
- `rank_news`：复用新闻相关性排序逻辑。
- `analyze_items`：复用单条财经新闻影响分析能力。
- `risk_route`：根据整体风险等级做条件路由。
- `risk_review`：复用已有风险和合规结果做高风险复核。
- `generate_report`：生成兼容旧 Market Pulse 风格的结构化结果。
- `repository`：保存历史报告，并把 `report_id` 附加到返回结果。

代码位置：

- `agent-python/app/api/market_pulse.py`：市场新闻分析相关 API。
- `agent-python/market_pulse/service.py`：API 调用入口。
- `agent-python/market_pulse/graph.py`：LangGraph 主流程编排。
- `agent-python/market_pulse/nodes/`：LangGraph 节点实现。
- `agent-python/market_pulse/analyzers/`：分析能力模块。
- `agent-python/market_pulse/rankers/`：业务排序策略。
- `agent-python/clients/`：真实外部服务客户端。
- `agent-python/market_pulse/repository.py`：报告持久化入口。
- `agent-python/storage/report_store.py`：SQLite 底层存储实现。
- `agent-python/safety/report_guard.py`：报告合规检查。

## 历史报告存储

SQLite 表名为 `reports`，核心字段包括：

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
query TEXT NOT NULL
news_count INTEGER NOT NULL DEFAULT 0
risk_level TEXT NOT NULL DEFAULT 'unknown'
summary TEXT NOT NULL DEFAULT ''
report_json TEXT NOT NULL
created_at TEXT NOT NULL
```

完整报告以 JSON 字符串保存到 `report_json`，中文内容使用 `ensure_ascii=False` 保存，便于查看和调试。

## 项目亮点

- 接入真实新闻源，先构建候选新闻池，再进行相关性排序。
- 支持单条新闻影响分析和批量 Market Pulse 分析。
- 支持公司维度 RSS 与 Google News RSS fallback，补充重点公司相关新闻。
- 使用 LangGraph 表达 Market Pulse 节点流转和风险分支。
- 对高风险结果保留额外复核节点，便于展示 Agent 工作流设计。
- 支持 SQLite 保存历史报告，并提供查询接口。
- 报告措辞聚焦趋势观察、风险提示和研究参考，避免包装成自动荐股系统。

## 免责声明

本项目输出内容仅用于学习和研究参考，不构成任何投资建议、交易建议或收益承诺。金融市场存在不确定性，实际投资决策应结合多方资料并由用户自行判断。
