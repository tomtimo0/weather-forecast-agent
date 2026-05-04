# 语义桥接评测报告

- 评测时间：20260504_165414
- 用例总数：**40**
- 评测集：`data/test_cases/semantic_bridge_bench.jsonl`
- 被测对象：`src.analysis.semantic_bridge.bridge_weather_dict`

## 一、三档消融总表

| 指标 | mode=off (baseline) | mode=rule_only | mode=rule_plus_rag |
|---|---|---|---|
| 覆盖率（生成 ≥1 label） | 0.0% | 100.0% | 100.0% |
| 标签条数一致 | 10.0% | 100.0% | 100.0% |
| 分级名准确率（grade） | 10.0% | 100.0% | 100.0% |
| 分级 ID 准确率（grade_id） | 10.0% | 100.0% | 100.0% |
| 引用率（must_cite 全中） | — | — | 100.0% |
| 场景过滤负例通过率 | — | — | 100.0% |
| source 字段匹配率 | — | — | 100.0% |
| baseline 文本为空率 | 100.0% | — | — |

## 二、按用例类别拆分（grade_id 准确率 / 引用率）

| 类别 | 用例数 | rule_only · grade_id | rule_plus_rag · grade_id | rule_plus_rag · 引用率 |
|---|---|---|---|---|
| fallback | 4 | 100.0% | 100.0% | 100.0% |
| multi | 2 | 100.0% | 100.0% | 100.0% |
| precipitation_12h | 5 | 100.0% | 100.0% | 100.0% |
| precipitation_24h | 11 | 100.0% | 100.0% | 100.0% |
| scene_filter | 2 | 100.0% | 100.0% | 100.0% |
| wind | 16 | 100.0% | 100.0% | 100.0% |

## 三、失败用例

> mode=off 下**预期**全部用例（除 fallback 外）覆盖率为 0%，这是 baseline 设计目标——用以与桥接模式对比。本节仅展示 rule_only / rule_plus_rag 的**真正失败**（即未达到设计目标的用例）。

rule_only 与 rule_plus_rag 模式下**无失败用例**，全部通过期望。

备注：mode=off 在 36 条非 fallback 用例上 **累计未达期望** 36 条 （36/36 = 100%），构成消融对照的负参照——证明不做桥接时纯靠 LLM 自由发挥无法稳定提供分级语义。

## 四、关键结论（自动摘要）

- **确定性分级覆盖**：rule_only 模式下 grade_id 准确率 100.0%，证明分类器表的阈值划分覆盖了所有有效输入。
- **权威引用注入**：rule_plus_rag 模式下引用关键字命中率 100.0%，证明 grade_id 硬链接能稳定从 KB 召回出处条款；场景不匹配时正确退化为 rule_only，不输出无关 citation。
- **baseline 对照**：mode=off 时 semantic_text 为空率 100.0%，完全依赖 LLM 自由发挥处理裸数值，作为消融实验的负参照。
