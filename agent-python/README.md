# Financial Agents Python Service

这是一个由 FastAPI 暴露接口、由 LangGraph 编排的财经新闻 Market Pulse Agent。

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

- `app/`: API 层，只创建 FastAPI、注册 router、处理请求响应。
- `market_pulse/service.py`: 业务入口，API 层只调用这里。
- `market_pulse/graph.py`: LangGraph 主流程编排。
- `market_pulse/nodes/`: 图节点实现，包括采集、排序、分析、风险复核、报告生成和保存。
- `market_pulse/analyzers/`: 单条新闻分析能力模块，不是独立乱跑的多 Agent。
- `market_pulse/rankers/`: 新闻排序策略。
- `clients/`: 外部服务访问，包括 LLM、新闻、RSS、行情数据。
- `market_pulse/repository.py`: Market Pulse 持久化入口。
- `storage/report_store.py`: SQLite 底层存储实现。
- `safety/report_guard.py`: 报告安全与合规检查。

## Run

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
