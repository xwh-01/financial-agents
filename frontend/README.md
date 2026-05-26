# Financial Agents Frontend

静态前端 SPA，纯 HTML + CSS + Vanilla JavaScript，无需 npm install 或构建步骤。

## 启动

```powershell
cd frontend
python -m http.server 5173
# 浏览器打开 http://127.0.0.1:5173
```

注意：需要先启动后端（默认 `http://127.0.0.1:8010`），否则 API 请求会失败。

## 后端地址

默认 `http://127.0.0.1:8010`，存储在 localStorage `mkt_base_url` 中。

如需修改，在浏览器控制台运行：
```js
localStorage.setItem("mkt_base_url", "http://your-backend:8010")
```

## 登录态

- 登录后 JWT token 存入 localStorage `mkt_token`
- 后续所有 API 请求自动携带 `Authorization: Bearer <token>`
- 未登录时自动跳转到 `#login`

## 页面路由

| Hash | 页面 | 说明 |
|------|------|------|
| `#login` | 登录 | Email + Password |
| `#register` | 注册 | 注册后跳转登录 |
| `#watchlists` | Watchlist 列表 | 创建/查看 watchlist |
| `#watchlist-detail/{id}` | Watchlist 详情 | 添加 item (ticker/topic/macro/commodity/custom) + 创建 job |
| `#jobs` | 任务列表 | 查看 job 状态 + 手动 Run |
| `#reports` | 报告列表 | 含 compliance_status 标识 |
| `#report-detail/{id}` | 报告详情 | disclaimer、summary、source items（含可点击 URL） |

## 人工验收清单

按以下步骤完整走通一遍：

1. 打开 `http://127.0.0.1:5173`
2. 点击 Register → 注册新账号
3. 跳转到 Login → 登录
4. 进入 Watchlists → 输入名称创建 watchlist
5. 点击 watchlist 名称进入详情
6. 添加 4 个 item：
   - item_type=ticker, symbol=NVDA, keyword=NVIDIA, display_name=NVIDIA
   - item_type=topic, keyword=AI chips, display_name=AI Chips
   - item_type=macro, keyword=Fed interest rate, display_name=Fed Interest Rate
   - item_type=commodity, keyword=gold, display_name=Gold
7. 点击 Create Report Job
8. 顶部点击 Jobs → 找到刚创建的 job → 点击 Run
9. 等待几秒后刷新（或再次点击 Jobs 菜单）
10. job 状态变为 succeeded 后，点击 View Report
11. 查看 Report Detail 页面：
    - 是否显示 disclaimer
    - 是否显示 compliance_status
    - source items 的 URL 是否可点击
    - 是否有"暂无结构化新闻来源"兜底

## 技术栈

- HTML5 + CSS3 (暗色主题)
- Vanilla JavaScript (ES2017+, async/await)
- Hash-based SPA routing
- No framework, no build step, no npm
