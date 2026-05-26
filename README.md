# Financial Agents

财经新闻追踪、噪声过滤、结构化报告、风险提示、来源追踪系统。不构成投资建议。

## 核心链路

```
注册/登录 → 创建 Watchlist → 添加 item (ticker/topic/macro/commodity/custom)
         → 创建 Report Job → 运行 Job → 查看 Reports
         → 查看 Report Items / Source URL → 展示 compliance_status / disclaimer
```

## 快速开始

### 本地启动

```powershell
# 后端
cd agent-python
.\.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010

# 前端（新终端）
cd frontend
python -m http.server 5173
# 浏览器: http://127.0.0.1:5173
```

### Docker Compose 启动

```powershell
copy .env.example .env
# 编辑 .env 填写 API keys
docker compose up -d
# 浏览器: http://127.0.0.1:5173
```

详细部署见 [DEPLOYMENT.md](DEPLOYMENT.md)。

### 验证脚本

```powershell
# 冒烟测试（自动注册→创建 watchlist→生成报告）
$env:BASE_URL = "http://127.0.0.1:8010"
python agent-python\scripts\smoke_test.py

# Ranker 质量评估
cd agent-python
python evals\ranker_eval.py

# Guard 合规检查
cd agent-python
python scripts\check_report_guard.py

# 新闻质量检查
cd agent-python
python scripts\check_news_quality.py

# 全体语法检查
python -m compileall agent-python
```

## 目录结构

```text
├── agent-python/            # 后端 Python 服务
│   ├── app/                 # FastAPI 入口 + API 路由
│   ├── auth/                # 认证 (JWT + bcrypt)
│   ├── watchlists/          # 关注列表业务
│   ├── report_jobs/         # 异步任务调度 (worker + scheduler)
│   ├── reports/             # 报告 CRUD + guard 合规
│   ├── market_pulse/        # LangGraph 新闻分析主流程
│   │   ├── nodes/           # LangGraph 节点
│   │   ├── rankers/         # 新闻排序 + source_weight
│   │   ├── filters/         # 去重 + freshness 过滤
│   │   └── utils/           # 标题/URL 归一化
│   ├── clients/             # 外部 API (LLM, News, RSS)
│   ├── storage/             # SQLite 存储层
│   └── scripts/             # smoke_test, eval, guard checks
├── frontend/                # 前端 SPA (纯 HTML/JS)
│   ├── index.html           # 入口
│   └── js/                  # api.js + app.js
└── docs/
```

## 后端技术栈

- FastAPI + Pydantic v2
- LangGraph (Market Pulse 主流程)
- SQLite (无需外部数据库)
- asyncio (scheduler + worker)
- bcrypt + PyJWT (认证)
- APScheduler-free (纯 asyncio 定时任务)

## 前端技术栈

- 纯 HTML + CSS + Vanilla JavaScript (无框架/无构建)
- Hash-based SPA routing
- JWT token localStorage
- 默认后端地址 `http://127.0.0.1:8010`

页面路由：`#login` `#register` `#watchlists` `#watchlist-detail/{id}` `#jobs` `#reports` `#report-detail/{id}`

详见 `frontend/README.md`。

## 新闻质量控制

- **URL 去重**：`normalize_url` 去除 utm_*/fbclid/gclid 跟踪参数
- **标题归一化**：`normalize_title` 小写/去标点/去多余空格
- **内容 hash**：`make_content_hash(title, url)` SHA256 去重
- **freshness 过滤**：超过 72h 丢弃，无时间戳保留但降权
- **source_weight**：Reuters/Bloomberg 1.0 → Unknown 0.5，加权到 relevance_score

```powershell
cd agent-python
python scripts\check_news_quality.py
```

## Ranker 质量评估

56+ 条标注样本，5 个 query，Precision@5/10 + Important Recall + Irrelevant Rate。

```powershell
cd agent-python
python evals\ranker_eval.py
# 输出: terminal + evals/ranker_eval_report.json + evals/ranker_eval_summary.csv
```

## 安全合规 Guard

禁止输出投资建议/收益承诺/交易指令，每个报告自动附加免责声明。

`compliance_status`: `safe` | `warning` | `unsafe`

```powershell
cd agent-python
python scripts\check_report_guard.py
```

## Worker & Scheduler

| 模式 | 启动方式 | 说明 |
|------|----------|------|
| 手动 | API `POST /api/report-jobs/{id}/run` | 通过前端或 curl 触发 |
| Worker | `python -m report_jobs.worker` | 独立进程，N 秒扫描执行 pending/failed jobs |
| Scheduler | `ENABLE_REPORT_SCHEDULER=true` | FastAPI 内运行，每天定时创建 daily jobs |

不依赖 Celery/Redis/Kafka，纯 SQLite + asyncio。

## License

Internal use only. Not financial advice.
