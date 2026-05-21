# 项目主链路 / Main Workflow

当前项目推荐把 LangGraph 版 Market Pulse 作为主链路：

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

主接口：

```http
POST /api/agent/market-pulse/langgraph
```

主流程文件：

```text
agent-python/market_pulse/graph.py
```

兼容入口仍保留：

```text
agent-python/workflows/langgraph_market_workflow.py
```

该旧文件只作为兼容层，新代码应优先调用 `market_pulse/service.py` 或 `market_pulse/graph.py`。

## LangGraph 节点职责

- `collect_news`：根据用户 query 搜索新闻；如果没有 query，则采集最新市场新闻。
- `rank_news`：对候选新闻做相关性排序，并限制进入分析阶段的新闻数量。
- `analyze_items`：复用单条新闻分析子流程，对每条入选新闻做实体、事件、市场影响、风险和合规分析。
- `risk_route`：根据整体风险等级做条件路由。
- `risk_review`：仅在整体风险为 high 时执行，汇总高风险原因和合规提醒。
- `generate_report`：基于分析结果生成趋势、研究参考建议和最终报告文本。
- `save_report`：将最终结果保存到 SQLite 历史报告表，并把 `report_id` 附加到返回结果。

## 目录职责

- `app/api/`：FastAPI 路由层，负责接收请求和返回响应。
- `market_pulse/service.py`：API 层调用入口，集中暴露单条新闻分析、Market Pulse、LangGraph Market Pulse、历史报告查询等服务函数。
- `market_pulse/graph.py`：当前推荐主流程，负责组装 LangGraph 节点和风险分支。
- `market_pulse/nodes/`：LangGraph 节点实现，包括新闻采集、排序、逐条分析、风险复核、报告生成和保存。
- `market_pulse/analyzers/`：分析能力模块，例如实体识别、事件分析、ticker 关联、市场影响分析、风险检查、合规检查和报告生成。它们不是多个独立乱跑的 Agent，而是被主 workflow 调用的能力单元。
- `market_pulse/rankers/`：Market Pulse 使用的新闻排序逻辑。
- `clients/`：真实外部服务客户端，包括 LLM、新闻、RSS 和市场行情。
- `market_pulse/repository.py`：报告持久化入口，底层仍调用 `storage/report_store.py`。
- `agents/`、`tools/`、`workflows/`、`schemas/`：第一阶段暂时保留为兼容层，后续第二阶段再逐步清理。

## 面试时推荐说法

这是一个由 LangGraph 编排的财经新闻 Market Pulse Agent。agents 目录中的模块是分析能力模块，不是多个独立乱跑的 Agent；主流程统一由 market_pulse/graph.py 编排，并通过 market_pulse/service.py 暴露给 FastAPI。
