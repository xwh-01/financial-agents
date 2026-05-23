# 财经新闻 Market Pulse Agent / Financial Agents

Financial Agents 是一个财经新闻研究参考项目。系统接入真实新闻源和 RSS 信息源，根据财经事件、公司动态、行业新闻和宏观信息，生成市场影响分析、风险提示和结构化报告。

本项目聚焦研究参考和风险提示，不做自动荐股，不承诺收益，也不构成投资建议。

## 项目主链路 / Main Workflow

当前推荐主接口：

```http
POST /api/agent/market-pulse/langgraph
```

当前推荐主流程文件：

```text
agent-python/market_pulse/graph.py
```

主链路：

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

## 当前结构

```text
agent-python/
├── app/                    # FastAPI 应用、配置、错误定义
│   └── api/                # health、Market Pulse、reports 路由
├── market_pulse/           # 核心业务域
│   ├── graph.py            # LangGraph 主流程
│   ├── state.py            # Graph State
│   ├── service.py          # API 层调用入口
│   ├── nodes/              # LangGraph 节点
│   ├── analyzers/          # 分析能力模块
│   ├── rankers/            # 排序策略
│   ├── schemas.py          # Pydantic 模型
│   └── repository.py       # 业务持久化入口
├── clients/                # LLM、新闻、RSS、行情数据等外部服务调用
├── config/                 # 公司新闻源配置
├── data/                   # SQLite 数据库运行目录
├── storage/                # 底层 SQLite 存储实现
├── safety/                 # 报告安全与合规检查
└── docs/                   # 主链路说明
```

`market_pulse/analyzers/` 中的模块是分析能力模块，不是多个独立乱跑的 Agent。主流程由 `market_pulse/graph.py` 统一编排，并通过 `market_pulse/service.py` 暴露给 FastAPI。

旧目录 `agents/`、`workflows/`、`tools/`、`schemas/` 不再作为当前结构使用。

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

当前数据源包括：

- `company rss_feeds`: `agent-python/config/company_feeds.json` 中配置的公司 RSS。
- Yahoo Finance ticker RSS: `https://finance.yahoo.com/rss/headline?s=<TICKER>`。
- NVIDIA official RSS: `https://nvidianews.nvidia.com/rss`。
- Google News RSS fallback: 使用 `search_queries` 构造搜索型 RSS。
- News API search endpoint: 用于通用新闻搜索和 Market Pulse 候选新闻补充。

RSS 源验证脚本：

```powershell
cd agent-python
.\.venv\Scripts\python.exe scripts\check_rss_sources.py
```

## 启动方式

打开虚拟环境并运行程序：

```powershell
cd agent-python
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

启动时会初始化 SQLite 数据库：

```text
agent-python/data/reports.db
```

## 接口示例

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

PowerShell 示例：

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/agent/market-pulse/langgraph" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"query":"Nvidia AI chips","max_items":3}'
```

### 历史报告

查询最近报告：

```http
GET /api/reports
```

查询单条报告：

```http
GET /api/reports/1
```

## 质量检查

```powershell
python -m compileall agent-python
```

cd "D:\desk top\agent\market-impact-agent-v2\agent-python"
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
