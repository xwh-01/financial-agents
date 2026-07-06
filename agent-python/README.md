# Financial Agents — Python Service

FastAPI + LangGraph + SQLite 后端。

## 产品主入口

| 入口 | 接口 |
|------|------|
| **Watchlist → 生成今日报告 → Report** | 用户点击生成今日报告；底层由 report job 创建并执行，仍由 `POST /api/watchlists/{id}/report-jobs` → `POST /api/report-jobs/{id}/run` → `GET /api/reports` 实现 |

其他接口（auth/watchlists/reports/today/jobs）均为本链路的辅助 API。

## 启动

```powershell
cd agent-python
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## 核心目录

```
app/api/reports.py          # 报告查询 + /api/reports/today
app/api/report_jobs.py      # Job 创建/运行/状态
app/api/watchlists.py       # 关注列表
app/api/auth.py             # 注册/登录
app/api/market_pulse.py     # Market Pulse Agent 接口（调试用）
market_pulse/graph.py       # LangGraph 编排
market_pulse/nodes/         # collect_news → rank_news → analyze_items → generate_report
market_pulse/filters/       # 去重 + freshness
market_pulse/rankers/       # 排序 + source_weight
reports/guard.py            # 合规扫描
report_jobs/worker.py       # 独立 worker
report_jobs/scheduler.py    # 自动创建 daily job
storage/report_store.py     # SQLite
```

## 验证脚本

```powershell
python scripts/smoke_test.py --daily-job-check   # 主链路冒烟
python scripts/check_news_quality.py              # 去重/freshness/source_weight
python scripts/check_report_guard.py              # 合规扫描
python evals/ranker_eval.py                       # Ranker 评估
python evals/agent_eval.py                        # MarketPulseDirectorAgent 评估
python -m compileall agent-python                 # 语法检查
```

## MarketPulseDirectorAgent

这个项目不是投资建议 Agent，不做荐股、买卖建议、收益承诺或自动交易。它是 Watchlist 驱动的财经新闻研究 Agentic Workflow，帮助用户从公开新闻中筛选重点、分析可能影响、提示风险，并保留来源和免责声明。

主流程仍然是可控的 Market Pulse workflow：`collect_news -> rank_news -> analyze_items -> risk_review -> generate_report`。新增的 `MarketPulseDirectorAgent` 位于 `market_pulse/agent/`，它在外层根据当前 state 选择下一步 action，不使用 LLM 决策，便于解释和测试。

Agent tools 复用现有 LangGraph 节点封装：采集、排序、逐条分析、风险审查和报告生成都沿用原业务逻辑；`compliance_guard` 复用既有 `reports.guard.apply_report_guard`，并对 Agent 明确禁用的收益承诺和买入话术做最终收口。

每次运行都会生成 Agent Trace，记录每一步 `action`、`reason`、`observation`、`metrics`、`error` 和时间戳。Trace JSON 保存到 `storage/agent_traces/{trace_id}.json`。

调试接口：

- `POST /api/market-pulse/agent-run` — 运行 Watchlist/query 驱动的 DirectorAgent workflow，返回完整 trace 和 final_result。
- `GET /api/agent-traces/{trace_id}` — 查看某次 Agent 执行轨迹。

Eval 位于 `evals/agent_eval.py` 和 `evals/agent_eval_cases.yaml`，验证 action 顺序、风险路由、合规 guard、来源追踪，以及空新闻/外部源失败时的 failed 或 degraded 路径。报告输出到 `evals/reports/agent_eval_report.md`。

## Legacy / Internal

以下接口保持可用但不作为产品主展示入口：

- `POST /agent/analyze` — 单条新闻分析
- `POST /agent/batch-analyze-news` — 批量分析
- `POST /agent/daily-brief` — 预设 query 简报
- `POST /agent/market-pulse` — 旧版 Market Pulse（非 LangGraph）
- `POST /api/agent/market-pulse/langgraph` — Agent 调试入口
- `POST /api/market-pulse/agent-run` — DirectorAgent trace 调试入口
