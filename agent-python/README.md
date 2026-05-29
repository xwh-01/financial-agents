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
python -m compileall agent-python                 # 语法检查
```

## Legacy / Internal

以下接口保持可用但不作为产品主展示入口：

- `POST /agent/analyze` — 单条新闻分析
- `POST /agent/batch-analyze-news` — 批量分析
- `POST /agent/daily-brief` — 预设 query 简报
- `POST /agent/market-pulse` — 旧版 Market Pulse（非 LangGraph）
- `POST /api/agent/market-pulse/langgraph` — Agent 调试入口
