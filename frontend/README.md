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
| `#watchlist-detail/{id}` | Watchlist 详情 | 添加 item (ticker/topic/macro/commodity/custom) + 生成今日报告 |
| `#jobs` | 任务状态 | 查看 report job 状态和调试；普通用户通常只需要在关注列表中点击生成今日报告 |
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
7. 点击“生成今日报告”
8. 前端会自动创建并执行 report job，生成后直接跳转到 Report Detail
9. 查看 Report Detail 页面：
    - 是否显示 disclaimer
    - 是否显示 compliance_status
    - source items 的 URL 是否可点击
    - 是否有"暂无结构化新闻来源"兜底

## 技术栈

- HTML5 + CSS3 (暗色主题)
- Vanilla JavaScript (ES2017+, async/await)
- Hash-based SPA routing
- No framework, no build step, no npm

## 新闻追踪板块选择器

Watchlist 详情页支持通过预设板块快速选择关注项，无需手动输入 item_type/symbol/keyword。

### 功能

- **10 大板块**：科技股、AI 与半导体、宏观政策、商品市场、财报与业绩、公司事件、监管与风险、市场情绪、行业主题、自定义关注
- **100+ 预设项**：每个预设包含 item_type/symbol/keyword/display_name
- **搜索**：输入关键词在所有 preset 中搜索（范围包括 label/keyword/display_name/symbol/category）
- **待添加列表**：点击 preset 先加入待添加列表，支持批量提交或移除
- **一键添加板块**：每个大类有"添加本板块全部"按钮
- **推荐组合**：4 套预设组合（科技股日报、AI 半导体追踪、宏观与黄金、原油与通胀）
- **防重复**：已添加/待添加的 preset 显示不同状态，不允许重复添加

### 数据源

`frontend/js/presets.js` — WATCHLIST_PRESETS, WATCHLIST_CATEGORIES, WATCHLIST_BUNDLES

### 用户流程

1. 打开关注列表详情页（`#watchlist-detail/{id}`）
2. 在"推荐组合"中选择一个组合，或在板块中选择单项
3. 查看待添加列表
4. 点击"批量添加到关注列表"
5. 点击“生成今日报告”
6. 底层由 report job 创建并执行实现，生成后进入报告详情页
