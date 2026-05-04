# 语义桥接评测报告

- 评测时间：20260504_203151
- 用例总数：**71**
- 评测档位：off, rule_only, rule_plus_rag
- 评测集：`data/test_cases/semantic_bridge_bench.jsonl`

## 一、3 档消融总表

| 指标 | mode=off (baseline) | mode=rule_only | mode=rule_plus_rag |
|---|---|---|---|
| 覆盖率（生成 ≥1 label） | 0.0% | 100.0% | 100.0% |
| 标签条数一致 | 5.6% | 100.0% | 100.0% |
| 分级名准确率（grade） | 5.6% | 100.0% | 100.0% |
| 分级 ID 准确率（grade_id） | 5.6% | 100.0% | 100.0% |
| 引用率（must_cite 全中） | — | — | 100.0% |
| 场景过滤负例通过率 | — | — | 100.0% |
| source 字段匹配率 | — | — | 100.0% |
| baseline 文本为空率（off 专属） | 100.0% | — | — |
| citation 出现率（LLM baseline 专属） | — | — | — |
| citation 标准号真实性（LLM baseline 专属） | — | — | — |

## 二、按用例类别拆分

| 类别 | 用例数 | rule_only · grade_id | rule_plus_rag · grade_id | rag · 引用率 |
|---|---|---|---|---|
| fallback | 4 | 100.0% | 100.0% | — |
| humidity | 8 | 100.0% | 100.0% | 100.0% |
| multi | 3 | 100.0% | 100.0% | 100.0% |
| precipitation_12h | 5 | 100.0% | 100.0% | 100.0% |
| precipitation_24h | 11 | 100.0% | 100.0% | 100.0% |
| scene_filter | 3 | 100.0% | 100.0% | — |
| temperature | 12 | 100.0% | 100.0% | 100.0% |
| visibility | 9 | 100.0% | 100.0% | 100.0% |
| wind | 16 | 100.0% | 100.0% | 100.0% |

## 三、失败用例

> mode=off 下**预期**全部非 fallback 用例覆盖率为 0%，是 baseline 设计目标，本节不重复展示其失败明细（详见关键结论部分的统计）。本节展示 rule_only / rule_plus_rag / llm_baseline 三档下**未达到期望**的用例。

以上 2 档模式**无失败用例**，全部通过期望。

备注：mode=off 在 67 条非 fallback 用例上 **累计未达期望** 67 条 （67/67 = 100%），构成消融对照的负参照。

## 四、关键结论（自动摘要）

- **确定性分级覆盖**：rule_only 模式下 grade_id 准确率 100.0%，证明分类器表的阈值划分覆盖了所有有效输入。
- **权威引用注入**：rule_plus_rag 模式下 must_cite 关键字命中率 100.0%，证明 grade_id 硬链接能稳定从 KB 召回出处条款；场景不匹配时正确退化为 rule_only，不输出无关 citation。
- **baseline 对照**：mode=off 时 semantic_text 为空率 100.0%，完全依赖 LLM 自由发挥处理裸数值，作为消融实验的负参照。
