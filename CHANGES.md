# Rank 系统改造总结

## 改造前 vs 改造后

### 旧 ranker（已废弃于主路径）
- 预制 80 个 ticker + 5 个 topic + 6 个 event 全局目录，不管用户 query 是什么都做全局匹配
- 来源权重 ×2.0、新鲜度打分、关键词命中，多个预设因子加权
- `select_representative_news` 硬规则终选（per_ticker=2, per_source cap）
- 问题：大量分数来自"我认为什么是好新闻"而非"用户问什么"

### 新 ranker（三层级联 pipeline）

```
candidate_news (300条)
    │
    ▼ Layer 1: coarse_filter (纯正则, <50ms, 同步)
    │   300 → 30
    │   从 query 提取关键词 → 覆盖率打分 → intent 强制召回 (每 intent ≥5条)
    │
    ▼ Layer 2: embedding_rerank (调 embedding API, 异步)
    │   30 → 15
    │   query 和 30 条标题摘要 → 向量化 → 余弦相似度排序
    │
    ▼ Layer 3: llm_rerank (一次 LLM 调用, 异步)
    │   15 → 8
    │   15 条打包成 prompt → LLM 通读后选 top 8，要求覆盖所有 topic 不垄断
    │
    ▼ selected_news → analyze_items
```

## 文件改动清单

### 新建文件
| 文件 | 职责 |
|------|------|
| `market_pulse/rankers/query_driven_ranker.py` | Layer 1: query 驱动关键词粗筛 |
| `market_pulse/rankers/embedding_ranker.py` | Layer 2: embedding API 语义精排 |
| `market_pulse/rankers/llm_reranker.py` | Layer 3: LLM 终选 + 多样性约束 |
| `market_pulse/analyzers/entity_event_resolver.py` | 合并 entity+event+risk → 一次 LLM 调用 |
| `market_pulse/analyzers/synthesize_report` | 新增: 8 条新闻合成全局市场洞察 |
| `config/ranker_rules.json` | 已保留，但新 ranker 不再依赖 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `market_pulse/nodes/rank_news.py` | async 三层串联 |
| `market_pulse/nodes/analyze_items.py` | 接入 init_market_cache + 失败追踪 |
| `market_pulse/nodes/generate_report.py` | async + 接入 synthesis 总结 |
| `market_pulse/analyzers/market_analyzer.py` | 加请求级缓存 `_cache` + `_failures` |
| `market_pulse/analyzers/ticker_linker.py` | 用 SECTOR_PEERS (90+ 条) 替代 3 个 if 块 |
| `market_pulse/analyzers/ticker_catalog.py` | 新增 SECTOR_PEERS 板块关联表 |
| `market_pulse/analyzers/report_generator.py` | 改进 prompt + synthesize_report |
| `market_pulse/workflows/single_news.py` | 适配合并后的 5 步分析链 |
| `market_pulse/service.py` | `run_fresh_opportunity_scan` 加 init_market_cache |
| `market_pulse/trace.py` | 加 ranked_news_count metadata |
| `app/config.py` | 加 embedding_api_key/base_url/model |
| `evals/ranker_eval.py` | 改用 coarse_filter + 新数据集 |
| `evals/ranker_eval_dataset.jsonl` | 重写: 119 条, 9 组 query, 含中文/自由文本/边缘 case |
| `evals/README.md` | 更新文档 |
| `tests/test_market_pulse_ranker.py` | 新增 Layer 1 4 个测试 |

### 不改文件
| 文件 | 原因 |
|------|------|
| `market_pulse/rankers/news_ranker.py` | 旧函数保留用于 legacy path |
| `market_pulse/graph.py` | 节点拓扑不变 |
| `market_pulse/nodes/collect_news.py` | 无改动 |
| `market_pulse/nodes/risk_review.py` | 无改动 |
| `market_pulse/state.py` | 无改动 |

## analyze_items 优化

| | 改前 | 改后 |
|---|---|---|
| 步骤数 | 7 | 5 |
| LLM 调用/条 | 3 次 | 2 次 |
| 风险判断 | 规则组合 (impact≥0.8→medium) | LLM 综合判断 |
| ticker 关联 | 3 个硬编码 if | 90+ SECTOR_PEERS 数据驱动 |
| 行情缓存 | 无 | 请求级 _cache 去重 |

### 单条新闻分析链 (5 步, 2 次 LLM)
```
输入: title + content + source + published_at

步骤1 ── LLM ──→ entity + event + risk (一次出三个结果)
步骤2 ── 规则 ──→ 公司名→ticker + topic→ETF + 板块关联
步骤3 ── API ──→ Alpha Vantage 行情 (有缓存)
步骤4 ── LLM ──→ 中文五段式报告 (含行情数据具体数值)
步骤5 ── 规则 ──→ 合规扫描 + 免责声明
```

## 最终报告结构

```
[全局市场总结]          ← LLM 合成，新增
  今日市场主要由财报行情和宏观政策信号主导...

---                    ← 分隔线

[详细信号列表]          ← build_market_signal_report
  一、核心结论
  二、市场观察信号
  1. NVDA 市场观察信号...
  2. TSLA 市场观察信号...
  ...

Note: Market data unavailable for: AAPL...    ← 行情失败显式标注
```

## 评测

### 运行方式
```powershell
cd agent-python
python evals/ranker_eval.py
```

### 数据集
- `evals/ranker_eval_dataset.jsonl` — 119 条, 9 组 query
- 含: 中文标题、自由文本 query、真实风格长标题、边缘 case (空标题/短内容)
- 干扰项: Telegram 骗局、加密货币 spam、菜谱、游戏、宠物、电影
- 标注: important / related / weakly_related / irrelevant 四档

### 指标
- Precision@5: 0.96 (前 5 条质量)
- Precision@10: 0.70 (长列表稳定性, 受子串误匹配影响)
- Important Recall@10: 1.00 (重要新闻不遗漏)
- Irrelevant Rate@10: 0.16 (噪声率, 待 Layer 2+3 消灭)

### 局限性
- 仅测 Layer 1 (coarse_filter), Layer 2+3 需要 API 不在离线 eval 范围内
- 119 条样本偏小, 定位是回归测试而非大规模 benchmark
