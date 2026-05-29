# Financial Agents

**Watchlist 驱动的 Market Pulse 财经新闻报告生成系统。**

财经新闻追踪 → 噪声过滤 → 结构化报告 → 风险提示 → 来源追踪。不构成投资建议。

## 主链路

```
登录/注册 → 创建 Watchlist → 选择关注项（9个板块/90+预设/搜索/推荐组合）
         → 用户点击生成今日报告，底层由 report job 创建并执行，生成后进入报告详情页
         → LangGraph Market Pulse 分析 → 保存报告 + report_items
         → 查看 Report Detail（disclaimer / compliance / source URL）
```

说明：Report Job 仍然是底层任务模型，Jobs 页面用于状态查看和调试。

## 快速启动

```powershell
# 终端 1 — 后端
cd agent-python
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010

# 终端 2 — 前端
cd frontend
python -m http.server 5173
# 浏览器 http://127.0.0.1:5173
```

Docker 部署见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 验证命令

```powershell
# 编译检查
python -m compileall agent-python

# 冒烟测试（全链路）
$env:BASE_URL = "http://127.0.0.1:8010"
python agent-python/scripts/smoke_test.py --daily-job-check

# Ranker 评估
cd agent-python && python evals/ranker_eval.py

# 合规检查
cd agent-python && python scripts/check_report_guard.py

# 新闻质量
cd agent-python && python scripts/check_news_quality.py
```

## 技术栈

- **后端**: FastAPI + LangGraph + SQLite + asyncio
- **前端**: 纯 HTML/CSS/JS（无框架，无构建）
- **部署**: Docker Compose（可选）
- **不依赖**: Redis / Celery / Kafka / PostgreSQL

## 更多文档

- 主链路验收: [docs/main_workflow_acceptance.md](docs/main_workflow_acceptance.md)
- 部署指南: [DEPLOYMENT.md](DEPLOYMENT.md)
- 前端说明: [frontend/README.md](frontend/README.md)
- 后端详情: [agent-python/README.md](agent-python/README.md)
