# Financial Agents · 完整项目汇报

> 结构：需求来源 → 解决思路 → 落地实现 → 反思。每个环节讲清楚"用户输入什么、系统做什么、输出什么"。

---

## 一、需求来源（~2 分钟）

### 1.1 从真实场景出发

2024 年底我开始关注美股。每天早上打开手机，Bloomberg、CNBC、Seeking Alpha、Reddit r/wallstreetbets —— 几百条推送。我一个散户投资者，关注的是 NVDA、AAPL、TSLA 这几家公司，加上 AI 芯片、美联储利率、黄金这三个主题。我需要回答的问题是：

**在我关注的这些公司和主题里，今天真正值得看的新闻是哪几条？**

这不是一个简单的关键词搜索能解决的问题。关键词搜索"NVDA"返回一百条结果，但其中八十条是重复转载、十篇是币圈蹭热度的垃圾、五篇讲的是游戏显卡而不是数据中心芯片、真正跟 AI 芯片市场需求变化相关的可能就两三条。另外，用户关注的是一个**列表**而不是一个关键词——我同时关注 NVDA 和 AAPL 和利率政策，我希望报告能覆盖所有这些方向，而不是只给我一种类型的新闻。

### 1.2 从现有工具的问题出发

Google News 的"关注主题"功能能帮你筛选新闻，但它不会告诉你每条新闻的影响是什么——"Fed holds rates steady" 这件事对 NVDA 意味着什么？利好还是利空？置信度多高？

Bloomberg Terminal 能做到但一年两万四千美元。市面上也有 AI 财经分析工具，但大多数是"输入一个股票代码，输出一段 AI 生成的文字"——没有结构化的证据链，没有不确定性说明，没有可复盘的执行轨迹。你不知道它为什么选了这几条新闻，也不知道它的结论能不能信。

### 1.3 从工程师的学习目标出发

除了解决实际需求，我做这个项目还有一个工程层面的目标：**我想把 LLM 从"调个接口拿一段文字"升级成一条有状态、可观测、可评测的 Agent 流水线。** 不是写一个 prompt 丢给 ChatGPT 就完事，而是设计一个有明确步骤、每步可独立验证、整个链路可追踪、质量可量化的系统。这是这个项目对我来说最大的工程训练价值。

---

## 二、整体设计思路（~1.5 分钟）

### 2.1 核心抽象：信息过滤管道

我把整个问题抽象成一条**多阶段信息过滤与增强管道**：

```
原始新闻流（每天几千条）
  → 采集：从多个来源汇聚，fail-soft
  → 去重：干掉转载和镜像
  → 排序：按用户关注的相关性从高到低排列
  → 分析：对每条新闻做结构化提取
  → 聚合：多条分析结果合并成一份报告
```

每一阶段缩小数据规模、增加信息密度。

### 2.2 用户交互模型

用户的核心操作路径是：

1. **创建一个关注列表**——告诉系统你关心哪些股票、公司、主题、宏观指标、大宗商品。比如："NVDA + AAPL + AI chips + Fed inflation + gold"
2. **触发生成报告**——手动点击"生成今日报告"，或配置每天早八点自动生成
3. **查看报告**——一份结构化的市场简报，包含核心结论、每条市场观察信号的证据链、风险提示、不确定性说明
4. **复盘**——查看这次执行的 trace，知道每个节点花了多长时间、外部 API 调了多少次

### 2.3 用户输入的具体参数

当用户触发生成报告时，系统收到的参数是：

```json
{
  "query": "ticker: NVDA\nticker: AAPL\ntopic: AI chips\nmacro: Fed inflation\ncommodity: gold",
  "max_items": 8,
  "tickers": ["NVDA", "AAPL"]
}
```

- `query`：结构化的关注意图字符串，每行一个意图，格式 `类型: 值`。类型可以是 ticker、company、topic、macro、commodity、custom
- `max_items`：最终分析多少条新闻。默认 8，范围 1-50
- `tickers`：额外关注的 ticker 列表，RSS 采集时会优先抓这些 ticker 相关的新闻

### 2.4 系统输出的最终产物

系统输出的是一份结构化的市场简报，核心字段：

```json
{
  "status": "completed",
  "query": "ticker: NVDA\n...",
  "generated_at": "2026-07-10T08:00:00+08:00",
  "total_news": 8,
  "candidate_news_count": 288,
  "filtered_news_count": 58,
  "analyzed_news_count": 8,
  "risk_level": "medium",
  "report": "一、核心结论\n本次扫描形成 5 条市场观察信号...",
  "market_signals": [
    {
      "signal_id": "signal-001-NVDA",
      "title": "NVDA 市场观察信号",
      "summary": "NVDA 出现偏正面的市场观察信号...",
      "event_type": "earnings",
      "risk_level": "low",
      "confidence": 0.72,
      "related_tickers": ["NVDA"],
      "entity_linking_reason": "NVDA 来自新闻标题、正文...",
      "risk_reason": "未识别到突出的结构化风险标记。",
      "uncertainty": "仍需结合后续公告、价格和成交量变化复核。",
      "evidence_summary": "该信号由 3 条新闻支持...",
      "supporting_articles": [
        {
          "title": "Nvidia's Next-Gen AI Chips...",
          "source": "CNBC",
          "url": "https://...",
          "published_at": "2026-07-10T06:30:00Z",
          "reason": "该新闻被分析流程识别为相关信号...",
          "relevance_score": 0.92
        }
      ],
      "signal_type": "market_signal"
    }
  ],
  "trace_id": "20260710_080000_a1b2c3d4",
  "trace_path": "traces/20260710_080000_a1b2c3d4.json"
}
```

这份报告有几个关键特征。第一，每条信号都有**证据链**——不是 AI 凭空说"NVDA 利好"，而是"基于 CNBC 某篇报道、Seeking Alpha 某篇分析，综合判断为偏正面"。第二，每条信号都有**不确定性说明**——置信度低的时候诚实说明"需要后续数据确认"，来源不完整的时候说明"部分来源缺少字段"。第三，整个报告可以**追溯**——trace_id 关联到执行记录，可以复盘每个节点。

---

## 三、采集阶段：三通道 fail-soft 落地实现（~2 分钟）

### 3.1 输入参数

采集节点的输入是 `MarketPulseGraphState` 中的 `query` 和 `tickers`：

```
query = "ticker: NVDA\nticker: AAPL\ntopic: AI chips\nmacro: Fed inflation\ncommodity: gold"
tickers = ["NVDA", "AAPL"]
```

### 3.2 三通道怎么落地

整个采集节点叫 `collect_news_node`，是一个 async 函数，返回更新后的 state。

**通道 1：Marketaux 关键词搜索。** 从 `query` 中提取出所有文本，拼接成搜索关键词，调用 Marketaux API。但这个通道默认关闭——配置项 `COLLECT_ENABLE_MARKETAUX=false`。为什么默认关？免费档每次运行大约 21 次查询请求，几分钟配额就打光，返回的新闻很多是几周前的，会在后续新鲜度过滤阶段被直接丢弃。这是从实际踩坑中学到的——Marketaux 免费档对管道是负贡献。

```python
if query and settings.collect_enable_marketaux:
    try:
        marketaux_items = await search_marketaux_news(
            query=query, limit=100, language="en"
        )
        candidate_news.extend(marketaux_items)
    except Exception as exc:
        print(f"marketaux failed: {exc}")  # fail-soft
```

**通道 2：公司 RSS + Google News fallback。** 从 `config/company_feeds.json` 加载三十多家公司的 RSS 配置。每条配置包含公司名、ticker、RSS feed URL 列表、Google News 搜索词列表。先并发抓取所有 RSS feed URL（每个 feed 最多取 20 条），如果总条数没达到 `min_news_count`（默认 10 条），自动启动 Google News fallback——用公司配置的搜索词拼接 Google News RSS URL 再抓一轮。

```json
// config/company_feeds.json 中的一条配置示例
{
  "company": "Nvidia",
  "ticker": "NVDA",
  "rss_feeds": [
    "https://seekingalpha.com/feed/symbol/NVDA.xml",
    "https://feeds.feedburner.com/nvidia-news"
  ],
  "search_queries": ["Nvidia AI chips", "NVDA stock", "Nvidia earnings"]
}
```

RSS feed 解析用的是 Python 的 `feedparser` 库。每个 entry 提取 title、summary/description、link、published/updated 四个字段。如果 feedparser 未安装或 feed 格式异常，同样 fail-soft，返回空列表。

**通道 3：多源财经 RSS。** 从六大财经源（CNBC、MarketWatch、NASDAQ、Seeking Alpha、Yahoo Finance、WSJ）抓取。每个源有多个 topic URL——比如 CNBC 有 16 个分类 feed（tech、markets、economy、finance 等），总共约五十多个 URL。这些 URL 也是逐个抓取，每个最多取 20 条。如果传入了 `tickers` 参数，在抓取后会按 ticker 过滤——只保留标题或正文中包含指定 ticker 的新闻。

### 3.3 数据归一化与去重

三条通道拿到的是三种格式的原始数据——Marketaux 返回 JSON API 格式，RSS 返回 XML feed 格式，Google News 返回 RSS 格式——需要统一成 `NewsItem` 这个 Pydantic 模型：

```python
class NewsItem(BaseModel):
    title: str
    title_zh: str = ""      # 中文翻译（可选）
    content: str = ""       # 正文/摘要
    source: str = ""        # 来源名称，如 "CNBC"
    url: str = ""           # 原始链接
    published_at: str = ""  # 发布时间 ISO 8601
    fetched_at: str = ""    # 抓取时间
    provider: str = ""      # 数据来源通道：marketaux / rss / google_news
    relevance_score: float = 0       # 排序阶段填充
    matched_tickers: list[str] = []  # 匹配到的 ticker
    matched_topics: list[str] = []   # 匹配到的主题
    source_weight: float = 0.5       # 来源可信度权重
    freshness_score: float = 0.0     # 新鲜度分数
```

统一后进入**三级去重**：

第一级 URL 去重。先 normalize——去掉 `utm_source`、`utm_medium`、`fbclid`、`gclid` 等追踪参数，去掉 fragment（`#` 之后的部分），去掉末尾斜杠，全部小写。第二级标题去重。去掉所有非字母数字字符（标点、emoji、特殊符号），全部小写，合并多余空格。相当于语义级别的去重——"NVIDIA's New AI Chip!!"和"nvidias new ai chip"会被识别为同一篇。第三级内容哈希去重。对标题加上 URL 做 SHA256 哈希，防止 URL 不同但内容完全相同的镜像转载。

去重时如果发现冲突——同一篇新闻通过不同通道进来了——用来源权重和发布时间做仲裁：来源可信度高的优先，同等来源时发布时间更新的优先。

### 3.4 候选池裁剪

去重后如果超过 300 条（`TARGET_CANDIDATE_MAX`），按三重优先级排序裁剪：

```python
def _candidate_pool_priority(item: NewsItem) -> tuple:
    published = parse_news_time(item.published_at)
    timestamp = published.timestamp() if published else 0.0
    content_len = len((item.content or "").strip())
    has_text = 1 if item.title and (content_len >= 40 or item.url) else 0
    return (timestamp, get_source_weight(item.source, item.url), has_text)
```

优先级：**新鲜度 > 来源可信度 > 内容完整性**。最新的新闻排前面，来源可靠的排前面，至少有标题和 40 字正文或有 URL 的排前面。没有标题或过旧或内容极短的条目在这个阶段也不会被丢弃——那留给 rank_news 阶段硬过滤——但它们在候选池里排在最后面。

### 3.5 采集阶段的输出

采集节点返回更新后的 state：

```python
{
    "candidate_news": [NewsItem, NewsItem, ...],  # ~300 条候选
    "collect_stats": {
        "marketaux": 0,           # Marketaux 贡献的数量（默认关闭所以是 0）
        "company_rss": 145,       # 公司 RSS 贡献的数量
        "market_rss": 143,        # 市场 RSS 贡献的数量
        "raw_candidate_count": 312,  # 去重前的原始总数
        "candidate_pool": 288        # 去重裁剪后的最终候选池大小
    }
}
```

---

## 四、排序阶段：三层管道落地实现（~3 分钟）

### 4.1 排序的输入

排序节点叫 `rank_news_node`，接收采集阶段的输出：

```
输入：
  candidate_news: list[NewsItem]  ← 288 条候选新闻
  query: str                       ← 用户的关注意图
  max_items: int                   ← 最终要分析多少条，默认 8
  market_pulse_max_analyze: int    ← 系统上限，默认 50

参数计算：
  coarse_limit = max(max_items * 2, 60)    = 60
  embedding_limit = max(max_items + 20, 40) = 40
  final_limit = max(1, min(max_items, market_pulse_max_analyze)) = 8
```

### 4.2 Layer 1：粗筛——意图解析与强制召回

**输入**：288 条 NewsItem + query 字符串
**输出**：60 条 NewsItem

第一步是**解析用户意图**。`query` 字符串是一个结构化格式：

```
ticker: NVDA
ticker: AAPL  
topic: AI chips
macro: Fed inflation
commodity: gold
```

解析器逐行处理。匹配正则 `^([A-Za-z_ ]{2,30}):\s*(.+)$`——冒号前是类型（ticker/topic/macro/commodity/company/custom），冒号后是值。值里面可能包含逗号、分号、竖线分隔的多个关键词，比如 `topic: AI chips, data center, semiconductor` 会被拆成三个独立意图，每个都是 `topic` 类型。

然后对 288 条新闻做硬过滤。目的不是排序，而是**剔除明显不合格的条目**，避免它们浪费后续的 embedding 和 LLM 调用。硬过滤规则：

1. **空标题**——`title.strip() == ""`——直接丢弃
2. **过旧**——发布时间超过 `max_age_days`（默认 7 天）——丢弃
3. **内容过短**——标题加正文拼接后不足 20 个字符——丢弃
4. **重复**——按 URL 归一化后的 key 去重

硬过滤后，对每条剩余的新闻打分。打分公式：

```
score = coverage * 10.0 + source_weight * 0.5 + freshness_bonus + title_hit_bonus
```

- **coverage**：命中的 query token 数 / query 总 token 数。NVDA 命中了 2 个 token（"nvda"），总 token 数是 5 个，coverage = 0.4
- **source_weight**：来源的可信度权重。CNBC 是 0.9，Reddit 是 0.2，无名博客是 0.1
- **freshness_bonus**：6 小时内 +1.0，24 小时内 +0.5
- **title_hit_bonus**：标题中命中的 query token 数 * 0.5

关键的工程决策是**按意图强制召回**。不是全局排序取 top 60，而是：

```python
# 第一步：每个意图取各自的 top PER_INTENT（默认 5 条），先占位
for intent in intents:
    intent_scored = [(item, score) for item, score in scored if intent_match(item, intent)]
    intent_scored.sort(reverse=True)
    for item, _ in intent_scored[:PER_INTENT]:
        recalled_keys.add(item_key(item))

# 第二步：从占位结果中按全局排序补入
for item, _ in scored:
    if item_key(item) in recalled_keys:
        result.append(item)

# 第三步：剩余名额从全局排序填充
for item, _ in scored:
    if len(result) >= coarse_limit: break
    if item_key(item) not in seen:
        result.append(item)
```

这个三段式选法保证了——即使 NVDA 相关的新闻排名极高，最多也只能占意图召回那 5 个名额加全局填充的一些名额，inflation 和 gold 的新闻也会有自己的 5 个保底名额。

### 4.3 Layer 2：Embedding 语义精排

**输入**：60 条 NewsItem + query 字符串
**输出**：40 条 NewsItem

这一层解决 Layer 1 无法处理的语义鸿沟——"美联储加息"和"Fed raises rates"在关键词层面完全不重叠，但在语义上是同一件事。

实现步骤：

```python
# 第一步：获取 query 的 embedding 向量
query_embedding = await call_embedding_api(query)  
# → [0.0123, -0.0045, 0.0234, ...]  # 1536 维向量

# 第二步：批量获取 60 条新闻的 embedding
texts = [f"{item.title} {item.content[:500]}" for item in layer1_output]
embeddings = await call_embedding_api(texts)
# → [[0.01, -0.00, ...], [0.02, 0.01, ...], ...]  # 60 个 1536 维向量

# 第三步：计算余弦相似度
for i, emb in enumerate(embeddings):
    similarity = cosine_similarity(query_embedding, emb)
    scored.append((layer1_output[i], similarity))

# 第四步：取 top 40
scored.sort(key=lambda x: x[1], reverse=True)
return [item for item, _ in scored[:40]]
```

降级策略：如果没配 embedding API key → 直接截断前 40 条。如果 API 调用失败 → 回退截断。如果 batch 返回数和输入数不匹配 → 回退截断。所有异常情况下管道都继续运行。

### 4.4 Layer 3：LLM 终选

**输入**：40 条 NewsItem + query 字符串 + final_limit
**输出**：8 条 NewsItem

这是最终的精确选择。prompt 设计：

```
System: You are a financial news relevance judge.
Given a user query and a list of candidate news articles,
select the most relevant ones.
Return ONLY a JSON array of the candidate numbers (1-based index)...
Rules:
- Select at most {limit} candidates.
- The query may contain multiple topics, tickers, or themes.
  You MUST ensure every distinct topic/ticker/theme in the query
  is covered by at least one selected article.
- Avoid selecting multiple articles about the exact same event.
- Skip articles that are clearly irrelevant.

User: User Query: ticker: NVDA, ticker: AAPL, topic: AI chips...

Candidates:
1. [CNBC] Nvidia's Next-Gen AI Chip Demand Surges...
   Nvidia reported record demand for its upcoming Blackwell...
2. [MarketWatch] Apple Delays Foldable iPhone to 2028...
   Apple has pushed back its foldable iPhone plans...
3. [Seeking Alpha] Gold Price Hits New High on Fed Pause Bets...
   Gold surged to a new all-time high as markets priced in...
...
40. [Yahoo Finance] 5 Best Gaming Keyboards for 2026...

Select the top 8 most relevant candidates.
```

LLM 返回 `[1, 3, 7, 12, 5, 8, 2, 15]`。

解析容错：

```python
def _parse_indices(response: str, max_items: int, limit: int) -> list[int]:
    # 第一步：尝试 JSON 解析
    match = re.search(r"\[[\d,\s]+\]", response)
    if match:
        arr = json.loads(match.group())
        return [int(x)-1 for x in arr if 1 <= int(x) <= max_items][:limit]
    
    # 第二步：fallback 到提取所有数字
    numbers = re.findall(r"\b(\d+)\b", response)
    return [int(x)-1 for x in numbers if 1 <= int(x) <= max_items][:limit]
    
    # 第三步：解析失败返回 None → 外层回退到截断前 8 条
```

### 4.5 排序阶段的输出

```python
{
    "ranked_news": [NewsItem, ...],    # 60 条（Layer 1 输出，用于 trace 统计）
    "selected_news": [NewsItem, ...]   # 8 条（Layer 3 输出，送入分析阶段）
}
```

---

## 五、分析阶段：单条新闻分析链（~2 分钟）

### 5.1 分析阶段的输入与并发模型

**输入**：8 条 selected_news
**输出**：8 条 DailyNewsAnalysis（每条包含分析结果或失败状态）

并发控制：`asyncio.Semaphore(concurrency)`，默认并发数 6。每条有一个独立超时，默认 90 秒。

```python
semaphore = asyncio.Semaphore(6)
analyzed_news = await asyncio.gather(
    *[_analyze_one_item(item, semaphore) for item in selected_news]
)
```

每条新闻走到 `_analyze_one_item`：

```python
async def _analyze_one_item(item, semaphore):
    async with semaphore:
        try:
            result = await asyncio.wait_for(
                run_single_news_analysis(AnalyzeRequest(
                    title=item.title, content=item.content,
                    source=item.source, published_at=item.published_at
                )),
                timeout=90
            )
            return DailyNewsAnalysis(news=item, analysis_result=result, status=result.status)
        except asyncio.TimeoutError:
            return DailyNewsAnalysis(news=item, analysis_result=None, 
                                     status="failed", error_message="analysis timed out after 90s")
        except Exception as exc:
            return DailyNewsAnalysis(news=item, analysis_result=None,
                                     status="failed", error_message=str(exc))
```

### 5.2 单条新闻分析链的 5 个步骤

**步骤 1：LLM 调用 #1——合并实体+事件+风险抽取**

输入是一篇新闻的标题和正文。System prompt 要求 LLM 输出严格的 JSON：

```
System:
You are a financial news analysis engine. Analyze the given news and 
extract structured information. Return ONLY valid JSON, no other text.

The JSON must have this structure:
{
  "entities": {
    "persons": ["..."],      // 提及的人物
    "companies": ["..."],    // 提及的公司名
    "tickers": ["..."],      // 明确的股票代码
    "topics": ["..."],       // 主题标签
    "confidence": 0.85       // 实体识别的置信度
  },
  "event": {
    "event_type": "...",     // earnings / macro_policy / regulation_risk / partnership / ...
    "summary": "...",        // 2-3 句话的事件摘要
    "sentiment": "positive", // positive / neutral / negative
    "impact_score": 0.75,    // 0-1 影响强度
    "confidence": 0.80       // 事件判断的置信度
  },
  "risk": {
    "risk_level": "low",     // low / medium / high
    "risk_flags": ["..."],   // 具体的风险标记
    "reason": "..."          // 风险判断的理由
  }
}
```

JSON 解析有完整的容错链：

```python
# 先尝试提取 ```json ... ``` 代码块
json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
if json_match:
    data = json.loads(json_match.group(1))
else:
    # 再尝试直接 JSON 解析
    data = json.loads(response)

# 用 Pydantic 做字段级校验和默认值填充
entity = EntityResult(**data["entities"])
event = EventResult(**data["event"])
risk = RiskResult(**data["risk"])
```

**步骤 2：规则驱动的 ticker 关联**

不调 LLM，纯规则。三个子步骤：

1. 公司名→ticker：维护了一个 ticker 目录（`TickerCatalog`），包含 100+ 家公司名到 ticker 的映射。比如 "Nvidia Corporation" → NVDA，"Apple Inc" → AAPL
2. Topic→ETF：按 topic 标签推荐相关的 ETF。比如 "semiconductor" → SMH，"AI" → BOTZ
3. 板块关联：90+ 条 `SECTOR_PEERS` 数据表。每个 ticker 定义了其同行（同板块竞争对手）和上下游。比如 NVDA 的 peers 包含 AMD、INTC、TSM（制造）、AVGO（网络芯片）

**步骤 3：Alpha Vantage 行情查询**

对所有关联的 ticker——包括直接关联、同行、ETF——查询最近 8 个交易日的日线数据。

```python
# 请求
GET https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=NVDA&apikey=xxx

# 返回处理
prices = normalize_alpha_vantage_daily(response)  
# → [{"date": "2026-07-09", "close": 145.23, "volume": 45231000}, ...]

returns = calculate_returns(prices)
# → {"return_1d": 0.021, "return_3d": -0.015, "return_7d": 0.045, "volume_change": 0.18}

# 同时抓 SPY 作为基准
spy_returns = calculate_returns(spy_prices)
relative_to_spy = returns["return_3d"] - spy_returns["return_3d"]

# 组装为 MarketMetric
metric = MarketMetric(
    return_1d=0.021, return_3d=-0.015, return_7d=0.045,
    volume_change=0.18, relative_to_spy_3d=0.008
)
```

请求级缓存——同一个 pipeline run 内，同一个 ticker 只请求一次。`asyncio.Lock` 保护 check-then-set 操作，防止并发任务重复请求。

**步骤 4：LLM 调用 #2——生成中文五段式报告**

把步骤 1-3 的所有结构化结果组装成 user prompt，system prompt 定义了严格的输出格式：

```
System:
你是一个金融舆情分析报告生成助手。
报告必须包含以下五个部分：
一、事件摘要：用 2-4 句话概括核心内容
二、关联资产：列出直接和间接关联的股票，说明原因
三、市场表现：明确写出具体涨跌幅数据。如果数据暂不可用，
   写为"数据暂不可用"，不要编造数字
四、风险提示：给出 1-3 条具体风险点
五、免责声明：必须包含"不构成投资建议"

禁止事项：
- 不得出现"建议买入""建议卖出""必涨""稳赚""保证收益"
- 不要把时间相关性说成因果关系
- 不要输出交易指令
- 不要用"约""大概"等模糊词
```

**步骤 5：合规扫描**

正则扫描 LLM 生成的报告，检查中英文禁用词列表。命中则替换为中性表述，末尾强制注入中文免责声明。这是硬规则执行，不依赖 LLM 自觉。

### 5.3 分析阶段的输出

```python
# 单条新闻分析结果 WorkflowResult
{
    "task_id": "uuid-xxxx",
    "status": "completed",  # completed / completed_with_compliance_warning / failed
    "entity_result": EntityResult(...),
    "event_result": EventResult(...),
    "ticker_links": TickerLinks(direct_tickers=["NVDA"], related_tickers=["AMD","TSM"], etfs=["SMH"]),
    "market_metrics": MarketMetrics(metrics={"NVDA": MarketMetric(...), "SPY": MarketMetric(...)}),
    "risk_result": RiskResult(risk_level="low", risk_flags=[], reason="..."),
    "compliance_result": ComplianceResult(passed=True, violations=[], sanitized_report="..."),
    "report": "一、事件摘要\nNvidia 最新财报显示数据中心业务...",
    "error_message": None
}

# analyze_items_node 的输出
{
    "analyzed_news": [DailyNewsAnalysis, ...],       # 8 条，含成功和失败
    "completed_results": [WorkflowResult, ...],       # 成功完成的（error_message is None）
    "overall_risk_level": "medium",                   # 所有 completed 中的最高风险等级
    "error_message": ""                               # 如果有行情失败，记录 here
}
```

分析阶段的 completed_results 数量可以小于 selected_news 数量——有些新闻 LLM 超时变为 failed，不影响其他。

---

## 六、报告生成与风险路由（~1.5 分钟）

### 6.1 趋势聚合

输入是 completed_results（一组 WorkflowResult），每个 WorkflowResult 里有一个或多个关联 ticker。按 ticker 分桶后，每个桶用加权聚合公式：

```
信号分 = 情绪分 × 影响强度 × 置信度 × 事件重要性

情绪分：positive=+1, neutral=0, negative=-1
事件重要性：earnings=1.35, macro_policy=1.25, regulation_risk=1.25,
           partnership=1.15, industry_demand=1.10, controversy=1.10,
           product_plan=0.95, unknown=0.75

风险惩罚：high=0.3, medium=0.15, low=0.0

市场确认分：1日涨跌和情绪同向 +0.06，3日跑赢/跑输 SPY +0.06，成交量放大 +0.04

方向判断：score >= 0.18 → 偏正面, score <= -0.18 → 偏负面, else → 中性观望
```

### 6.2 MarketSignal 生成

每个 TickerTrend 被包装成 MarketSignal。关键字段：

- `signal_id`：`signal-{序号}-{ticker}`，如 `signal-001-NVDA`
- `title`：`{ticker} 市场观察信号`
- `evidence_summary`：如"该信号由 3 条新闻支持。代表性来源：Nvidia's Next-Gen..."
- `entity_linking_reason`：解释这个 ticker 为什么被关联——"NVDA 来自新闻标题、正文或分析阶段的 ticker/entity linking"
- `risk_reason`：风险标记拼接，或"未识别到突出的结构化风险标记"
- `uncertainty`：根据多个维度自动生成——置信度低、缺少来源、来源不完整、行情确认不足——每种情况对应一条说明
- `supporting_articles`：最多 3 篇支持来源，每篇包含标题、来源名、URL、发布时间、关联理由、相关性分数

### 6.3 风险路由

`risk_route` 节点读取 `overall_risk_level`：

```python
def route_after_risk(state):
    if state.get("overall_risk_level") == "high":
        return "risk_review"      # 走风险复核分支
    return "generate_report"      # 直接生成报告
```

如果是 high，`risk_review` 节点遍历所有 `analyzed_news`，收集高风险条目的 risk_reason 和合规 violation。这些内容追加到报告末尾的"Risk review"部分。非 high 时，`risk_review` 在 trace 中记录为 skipped。

### 6.4 全局市场总结

如果 completed_results 至少有 3 条，额外调一次 LLM 做 synthesis。输入是所有完成分析的 full report text + 趋势汇总，输出 200-300 字的中文全局总结。System prompt 要求"不要逐条罗列，要跨事件寻找关联和脉络"、"指出值得关注的风险点和不确定性"。

### 6.5 合规守卫与落库

最终 report 输出前，调用 `apply_output_compliance_guard`。扫描中英文禁用词——"建议买入""sell now""recommend buying""guaranteed return"等——命中则替换。自动注入免责声明。保存到 `reports` 表（总体）和 `report_items` 表（每条分析来源）。

### 6.6 报告阶段的最终输出

```python
{
    "result": {
        "status": "completed",
        "query": "ticker: NVDA\n...",
        "generated_at": "2026-07-10T08:05:32+08:00",
        "total_news": 8,
        "candidate_news_count": 288,
        "filtered_news_count": 58,
        "analyzed_news_count": 8,
        "risk_level": "medium",
        "overall_risk_level": "medium",
        "risk_review_notes": [],
        "trends": [TickerTrend(NVDA, direction=偏正面, confidence=0.72, ...), ...],
        "market_signals": [MarketSignal(...), ...],
        "report": "一、核心结论\n本次扫描形成 5 条市场观察信号...",
        "report_id": 42,
        "api_calls": {
            "marketaux": {"logical_calls": 0, "http_attempts": 0},
            "alpha_vantage": {"logical_calls": 6, "http_attempts": 8}
        },
        "trace_id": "20260710_080000_a1b2c3d4"
    }
}
```

---

## 七、可观测性：trace 的落地细节（~1 分钟）

两层 trace 的实现：

**第一层：trace_node 装饰器**。每个 LangGraph 节点函数被装饰器包裹。装饰器的逻辑是：

```python
def trace_node(node_name, node_fn):
    async def wrapped(state):
        start = datetime.now(timezone.utc)
        input_count = _count_inputs(state)  # 统计候选数量
        try:
            result = await node_fn(state)
            duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            output_count = _count_outputs(result)
            _add_trace_event(state, node_name, "completed", duration_ms, input_count, output_count)
            return result
        except Exception as exc:
            duration_ms = ...
            _add_trace_event(state, node_name, "failed", duration_ms, input_count, 0, error=str(exc))
            raise
    return wrapped
```

**第二层：数据库 trace**。三张表——`report_traces`（总体）、`report_trace_steps`（节点明细）、`api_call_stats`（API 计数）。前端用瀑布图展示——每个节点是一根横向柱子，长度代表耗时比例，失败节点标红，跳过节点标灰。API 计数区分 `logical_calls` 和 `http_attempts`。

---

## 八、评测体系（~1 分钟）

Ranking 评测 119 条标注数据集。数据生成方式是——9 组 query 分别用 Layer 1 排序，人工标注每条新闻的相关性四档。评测指标——Precision@5=0.96、Important Recall@10=1.00、Irrelevant Rate@10=0.16。

Agent 评测模拟 5 个 Agent 工具调用场景——正常流程、空新闻降级、高风险触发审查、步数耗尽、多工具组合。用 YAML 定义 case，Pydantic 校验输出。

---

## 九、反思（~0.5 分钟）

这个项目教会我几件事。第一个，**Agent 系统的质量评测不应该只靠"跑通了"**——需要量化指标。第二个，**外部依赖不可靠是常态**——Marketaux 免费档的限流、RSS feed 的格式变化、LLM 的随机性——系统需要在每个环节设计降级路径。第三个，**模块级全局状态在 asyncio 并发下是隐患**——`contextvars` 和 `asyncio.Lock` 是最小成本的解决方案。

这个项目最大的工程价值，是把 LLM 从"调个接口"做成了一条有状态、可观测、可评测、有明确边界的 Agent 流水线。每个阶段的输入输出都是类型安全的，每个节点的运行都能被追踪，每次改动的效果都能被量化。

---

以上是我的完整汇报，请各位提问。

---

*项目输出为市场观察与风险观察，不构成任何投资建议。*
