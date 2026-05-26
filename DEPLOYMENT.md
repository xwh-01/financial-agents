# Deployment Guide

## 本地直接启动

### 后端

```powershell
cd agent-python
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

### 前端

```powershell
cd frontend
python -m http.server 5173
# 浏览器: http://127.0.0.1:5173
```

## Docker Compose 启动

```powershell
# 1. 复制环境变量模板
copy .env.example .env

# 2. 编辑 .env，至少设置 JWT_SECRET
notepad .env

# 3. 启动所有服务
docker compose up -d

# 4. 查看日志
docker compose logs -f backend

# 5. 停止
docker compose down
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8010 |
| Health Check | http://127.0.0.1:8010/healthz |

## 环境变量说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REPORTS_DB_PATH` | `agent-python/data/reports.db` | SQLite 数据库路径 |
| `JWT_SECRET` | 开发环境有默认值 | JWT 签名密钥，生产必须更换 |
| `LLM_API_KEY` | (空) | OpenAI 兼容 API Key |
| `LLM_BASE_URL` | `https://api.openai.com/v1/chat/completions` | LLM API 地址 |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `NEWS_API_KEY` | (空) | 新闻 API Key (NewsAPI / Marketaux) |
| `NEWS_BASE_URL` | (空) | 新闻 API 地址 |
| `CORS_ALLOWED_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | 允许的前端域名（逗号分隔） |
| `ENABLE_REPORT_SCHEDULER` | `false` | 是否启用每日定时任务 |
| `DAILY_REPORT_HOUR` | `8` | 每日创建 job 的小时 |
| `DAILY_REPORT_MINUTE` | `0` | 每日创建 job 的分钟 |

## API Key 配置

`.env.example` 不含真实 key。启动前必须将 `.env.example` 复制为 `.env` 并填写：

```env
LLM_API_KEY=sk-your-key-here
NEWS_API_KEY=your-newsapi-key
NEWS_BASE_URL=https://newsapi.org/v2/everything
```

`.env` 已加入 `.gitignore`，不会被提交到仓库。

## SQLite 数据持久化

Docker Compose 通过 volume 映射持久化数据：

```yaml
volumes:
  - ./data:/data
```

- 数据库文件路径：`/data/reports.db`（容器内）
- 映射到宿主机：`./data/reports.db`（项目根目录）
- `docker compose down` 不会删除 volume，数据保留
- 如需重置数据：`rm -rf ./data`

## 前端访问说明

- 前端通过 nginx 在 80 端口提供静态文件
- 宿主端口映射为 5173（开发习惯）
- 前端所有 API 请求走浏览器直连后端 8010 端口
- 确保 CORS 已配置（`.env` 中 `CORS_ALLOWED_ORIGINS`）

## Health Check

```powershell
# 本地
curl http://127.0.0.1:8010/healthz

# Docker
docker compose exec backend curl http://localhost:8010/healthz
```

## 常见问题

### 端口占用

`8010` 或 `5173` 被占用时，修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "8011:8010"   # 改为其他端口
```

### Docker Desktop 未启动

Windows/Mac 需要先启动 Docker Desktop，再运行 `docker compose up`。

### API Key 缺失

未配置 `NEWS_API_KEY` 时，后端可启动但新闻采集接口（`/api/agent/market-pulse/langgraph`）会返回错误。RSS 源不受影响。

### CORS 错误

浏览器控制台出现 CORS 错误时：
1. 检查 `.env` 中 `CORS_ALLOWED_ORIGINS` 是否包含前端地址
2. 重启后端：`docker compose restart backend`

### SQLite 数据文件位置

```powershell
# 本地开发
agent-python/data/reports.db

# Docker 部署
./data/reports.db    (映射到容器 /data/reports.db)
```
