# 财经时事影响分析 Agent / Financial Agents

## 项目简介

Financial Agents 是一个用于财经新闻研究参考的 Agent 项目。项目接入真实新闻源，根据财经时事、宏观事件、行业新闻和公司动态，分析新闻可能带来的市场影响，并输出趋势观察、风险提示和结构化研究报告。

本项目仅用于学习和研究参考，不构成投资建议。

## 核心流程

新闻采集 → 相关性排序 → 事件识别 → 市场影响分析 → 风险检查 → 报告生成

## 技术栈

- Python
- FastAPI
- Pydantic
- HTTPX
- News API
- LLM API
- HTML
- JavaScript

## 目录结构

```text
.
├── agent-python/
│   ├── agents/              # 单步 Agent：实体识别、事件分析、风险检查、报告生成等
│   ├── app/                 # FastAPI 应用入口和路由
│   ├── schemas/             # 请求、响应和工作流数据模型
│   ├── tools/               # 新闻采集、新闻排序、市场数据等工具
│   └── workflows/           # 单条新闻分析和 Market Pulse 工作流
├── frontend/                # 简单前端页面
└── README.md
```

## 启动方式

```bash
cd agent-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后可访问本地 FastAPI 服务，默认地址通常为：

```text
http://127.0.0.1:8000
```

## 接口示例

### POST /agent/market-pulse

请求示例：

```json
{
  "limit": 50,
  "language": "en",
  "translate_to_zh": false,
  "max_items": 5
}
```

响应会包含候选新闻数量、排序后新闻数量、实际分析新闻数量、趋势观察、风险提示和报告内容。

## 项目亮点

- 接入真实新闻源，先构建候选新闻池，再进行相关性排序。
- 面向财经时事、宏观事件、行业新闻和公司动态做分层分析。
- 对单条新闻执行实体识别、事件识别、市场影响分析、风险检查和报告生成。
- Market Pulse 工作流保留候选数量、过滤数量和实际分析数量，便于展示分析过程。
- 报告措辞聚焦趋势观察、风险提示和研究参考，避免将结果包装成自动荐股系统。

## 免责声明

本项目输出内容仅用于学习和研究参考，不构成任何投资建议、交易建议或收益承诺。金融市场存在不确定性，实际投资决策应结合多方资料并由用户自行判断。
