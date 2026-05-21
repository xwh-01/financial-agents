# 项目主链路 / Main Workflow

当前项目推荐把 LangGraph 版 Market Pulse 作为主链路：

```text
User Query
  ↓
FastAPI Route
  ↓
LangGraph Market Pulse Workflow
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
agent-python/workflows/langgraph_market_workflow.py
```

## LangGraph 节点职责

- `collect_news`：根据用户 query 搜索新闻；如果没有 query，则采集最新市场新闻。
- `rank_news`：对候选新闻做相关性排序，并限制进入分析阶段的新闻数量。
- `analyze_items`：复用单条新闻分析子流程，对每条入选新闻做实体、事件、市场影响、风险和合规分析。
- `risk_route`：根据整体风险等级做条件路由。
- `risk_review`：仅在整体风险为 high 时执行，汇总高风险原因和合规提醒。
- `generate_report`：基于分析结果生成趋势、研究参考建议和最终报告文本。
- `save_report`：将最终结果保存到 SQLite 历史报告表，并把 `report_id` 附加到返回结果。

## 目录职责

- `agents/`：分析能力模块，例如实体识别、事件分析、ticker 关联、市场影响分析、风险检查、合规检查和报告生成。它们不是多个独立乱跑的 Agent，而是被主 workflow 调用的能力单元。
- `tools/`：底层工具模块，例如新闻搜索、新闻采集、RSS 聚合、新闻排序、行情数据、翻译和 LLM client。
- `workflows/`：流程编排层。`langgraph_market_workflow.py` 是当前推荐主流程；`market_impact_workflow.py` 是单条新闻分析子流程；`market_pulse_workflow.py` 是旧版普通函数流程，继续保留用于兼容。

## 面试时推荐说法

这是一个由 LangGraph 编排的财经新闻 Market Pulse Agent。agents 目录中的模块是分析能力模块，不是多个独立乱跑的 Agent；主流程统一由 langgraph_market_workflow.py 编排。
