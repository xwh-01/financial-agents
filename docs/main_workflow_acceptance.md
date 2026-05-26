# 主链路验收文档

## 项目定位

Financial Agents 是一个 **Watchlist 驱动的 Market Pulse 财经新闻报告生成系统**。

用户配置关注列表（股票代码、行业主题、宏观政策、商品市场），系统自动抓取相关财经新闻，通过 LangGraph Market Pulse Agent 分析排序，生成结构化市场脉冲报告，并标注合规状态和免责声明。

不构成投资建议。

## 主链路步骤

| 步骤 | 操作 | 前端页面 | 后端模块 |
|------|------|----------|----------|
| 1 | 注册/登录 | `#register` → `#login` | `app/api/auth.py` → `auth/` |
| 2 | 创建 Watchlist | `#watchlists` | `app/api/watchlists.py` |
| 3 | 选择关注项 | `#watchlist-detail/{id}` | `app/api/watchlists.py` + 预设来自 `frontend/js/presets.js` |
| 4 | 创建 Report Job | Watchlist 详情页 "创建报告任务" | `POST /api/watchlists/{id}/report-jobs` → `report_jobs/` |
| 5 | 运行 Job | `#jobs` 页面 "Run" 按钮 | `POST /api/report-jobs/{id}/run` → `report_jobs/service.py` → LangGraph |
| 6 | 查看今日报告 | `#today` 或 `#reports` | `GET /api/reports/today` → `reports/` |
| 7 | 查看报告详情 | `#report-detail/{id}` | `GET /api/reports/{id}` → 含 disclaimer/compliance/source items |

## 本地启动

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

## 完整跑通流程

1. 打开 http://127.0.0.1:5173
2. 点击 Register → 输入邮箱和密码 → 注册
3. 跳转 Login → 登录
4. 进入 Watchlists → 创建 watchlist（名称如 "Morning Brief"）
5. 点击 watchlist → 进入详情页
6. 在推荐组合中点击"科技股日报"或手动选择关注项
7. 在板块中选择 NVDA、AI chips、Fed interest rate、gold
8. 点击"批量添加"
9. 点击"创建报告任务"
10. 跳转到 Jobs 页面 → 点击 Run
11. 等待 job 变为 succeeded
12. 点击 View Report → 查看详情
    - 确认有 disclaimer
    - 确认有 compliance_status
    - 确认 source items 可点击
13. 进入 Today 页面确认今日报告列表

## 常见失败点

| 现象 | 原因 | 解决 |
|------|------|------|
| 注册失败 `[object Object]` | 后端返回验证错误 | 使用正确邮箱格式 + 8 位以上密码 |
| 登录后页面空白 | 未刷新 | Ctrl+Shift+R 强制刷新 |
| 前端连接不上后端 | 后端未启动或端口不同 | 确认 `uvicorn` 在 8010 端口运行 |
| 搜索/板块不显示 | `presets.js` 缺失 | 确认 `frontend/js/presets.js` 存在且被 `index.html` 引用 |
| Job 创建后 Run 失败 | News API Key 未配置 | 检查 `.env` 中 `NEWS_API_KEY` |
| Job succeeded 但 report items 为 0 | LangGraph 输出格式与 extract_report_items 不匹配 | 检查后端日志 |
| 报告详情无 source items 显示 | `report_items` 表未写入 | 确认 `reports/service.py` 的 `save_report_items` 被调用 |
| CORS 错误 | 后端 CORS 未 Allow | 确认 `CORS_ALLOWED_ORIGINS` 包含前端地址 |
| 端口占用 | 上次进程未退出 | `taskkill /F /IM python.exe` |

## 相关文档

- [README.md](../README.md) — 项目总览
- [agent-python/README.md](../agent-python/README.md) — 后端详情
- [frontend/README.md](../frontend/README.md) — 前端详情
- [DEPLOYMENT.md](../DEPLOYMENT.md) — 部署指南
