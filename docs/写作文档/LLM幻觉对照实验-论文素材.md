# LLM 自由发挥 vs 双通路 RAG 桥接：消融对照实验

> **用途**：本文档作为毕业论文素材，记录在 `data/test_cases/semantic_bridge_bench.jsonl`
> （40 条用例）上对比 4 档处理方式的实证结果，重点展示「LLM 自由发挥」时
> 出现的典型幻觉模式，作为论文 Q3 章节核心实证。
>
> **评测时间**：2026-05-04
> **被测对象**：`bridge_weather_dict`（off / rule_only / rule_plus_rag 三档）
> + `run_llm_baseline`（GLM-5.1，第 4 档）
> **评测脚本**：`experiments/eval/run_bridge_eval.py`
> **结果文件**：`experiments/results/semantic_bridge_eval_latest.md`

---

## 一、核心数据：4 档消融对比

| 指标 | mode=off | mode=rule_only | mode=rule_plus_rag | mode=**llm_baseline** |
|---|---:|---:|---:|---:|
| 覆盖率（生成 ≥1 label） | 0.0% | 100.0% | 100.0% | **97.2%** |
| 标签条数一致 | 10.0% | 100.0% | 100.0% | **97.5%** |
| **分级名准确率（grade）** | 10.0% | 100.0% | 100.0% | **85.0%** |
| **分级 ID 准确率（grade_id）** | 10.0% | 100.0% | 100.0% | **10.0%** |
| **must_cite 关键字命中率** | — | — | 100.0% | **42.4%** |
| 场景过滤负例通过率 | — | — | 100.0% | **50.0%** |
| source 字段匹配率 | — | — | 100.0% | **0.0%** |
| **citation 出现率** | — | — | — | **100.0%** |
| **citation 标准号真实性（粗粒度）** | — | — | — | **100.0%** |

> 「citation 出现率」与「citation 标准号真实性」是 LLM baseline 专属指标：
> 前者表示 LLM 是否给出了 citation 字段，后者检查 citation 中是否含有
> 一个真实存在的国标 / 行业标准号（依据
> `experiments/eval/metrics.py::KNOWN_REAL_STANDARDS` 白名单）。

---

## 二、关键发现：LLM 幻觉的「真实却错」悖论

LLM baseline **同时呈现两个看似矛盾的指标**：

```
citation 标准号真实性 = 100.0%   ← 粗粒度：LLM 给的标准号都真实存在
must_cite 关键字命中率 = 42.4%   ← 严格：与 KB 期望的标准号 + 条款号一致
```

差距 **57.6%** 即是论文 Q3 章节最有价值的实证：

> **LLM 知道有哪些标准（标准号都是真实的），但不知道该用哪一个、哪一条**。
> 这正是"看似权威、实则错引"的经典幻觉模式——比"完全编造"更危险，因为
> 它会通过用户对权威标准号的信任绕过审查。

---

## 三、典型幻觉案例归类

下面五类是评测中真实出现的幻觉模式，每类至少给出 2 个例子。

### 3.1 标准号对、**条款号错**（最典型）

LLM 知道关于"高处作业禁令"应引 JGJ 80-2016，但每次给出的条款号都不一样，
且都不是真实的 §3.0.8（这恰好是我们之前在 `知识库标准核对表-论文素材.md`
中人工核对发现的同类错误）。

| 用例 | 输入 | LLM 给出的 citation | 真实条款 |
|---|---|---|---|
| `wind_006_strong` | 6 级强风 | "JGJ 80-2016 **§5.1.3**" | §3.0.8 |
| `wind_007_near_gale` | 7 级疾风 | "JGJ 80-2016 **§5.1.6**" | §3.0.8 |
| `wind_008_gale` | 8 级大风 | "JGJ 80-2016 **§3.0.3**" | §3.0.8 |
| `wind_014_int_field` | windScale=8（int 字段） | "JGJ 80-2016 **§3.0.5**" | §3.0.8 |

> **注意**：LLM 在 4 次需要引用 JGJ 80 的场合给出了 4 个不同的条款号
> （5.1.3 / 5.1.6 / 3.0.3 / 3.0.5），全部错误。这是典型的**"模式记忆"
> 幻觉**——LLM 知道 JGJ 80 的条款号大致是 `§3.0.X` 或 `§5.1.X` 形式，
> 就在合理样式空间里随机生成。

### 3.2 自创等级 / 越界处理失败

LLM 在边界与越界数值上倾向于"创造"标准并不存在的等级。

| 用例 | 输入 | LLM 输出 | 实际国标规定 |
|---|---|---|---|
| `rain24_001_trace` | 0.05mm | grade="**微量降水（零星降水）**"，并称"GB/T 28592-2012 §4.1 规定 <0.1mm 为微量降水，不构成小雨" | GB/T 28592 实际**不区分**"微量降水"等级，<0.1mm 仅记录不分级 |
| `rain12_005_overflow` | 12h 100mm | grade="**大暴雨**" | GB/T 28592 的 12h 表只到"暴雨"（≥30mm），**没有 12h 大暴雨档** |
| `wind_015_overflow` | windScale=15 | grade="**15级（超强台风级风力）**"，并引"GB/T 19201-2006 §3 热带气旋等级" | 蒲福风级最高 12 级；15 级是热带气旋分类，不是蒲福风级，LLM **混用了两个标准** |

### 3.3 grade 名误名（与国标用词不一致）

LLM 凭印象给的中文名虽然语义近似，但与国标条文用词不严格相符。

| 用例 | LLM 给出 | GB/T 28591-2012 标准用词 |
|---|---|---|
| `wind_005_fresh`（5 级） | "**清风**" | "**清劲风**"（fresh breeze） |
| `multi_002_rain12_wind` | "**清风（劲风）**" | "**清劲风**" |

### 3.4 grade_id 100% 凭印象编造

| 用例 | LLM 给出的 grade_id | KB 真实 ID |
|---|---|---|
| 24h 大雨 | `heavy_rain` / `heavy_rain_12h` | `grading_precip_24h_heavy` |
| 12h 暴雨 | `torrential_rain` | `grading_precip_12h_rainstorm` |
| 5 级风 | `beaufort_5` | `grading_wind_beaufort_5` |
| 特大暴雨 | `6` | `grading_precip_24h_extreme_rainstorm` |
| 微量降水 | `trace` | （KB 中无此分级） |

> 36 条非 fallback 用例里，LLM **没有一个 grade_id 与 KB 命名约定一致**
> （只有 4 条 fallback 用例因为正确返回空 labels 而被记为通过，得到
> 10.0% 准确率）。这论证了**KB 内部寻址必须靠硬链接，不能交给 LLM 猜**。

### 3.5 场景过滤失败：无法在不适用场景下沉默

桥接架构通过 `applicable_scene` 字段在场景不匹配时**主动**不产出 citation；
而 LLM baseline 在所有场景下都倾向于产出 citation，无法区分"该说"与
"不该说"。

| 用例 | scene | KB 该条 applicable_scene | 期望 | LLM 实际 |
|---|---|---|---|---|
| `scene_001_rain_offscene` | 高空作业 | 出行/施工/农业/防汛（不含高空作业） | 不输出 GB/T 28592 citation | 仍输出"GB/T 28592-2012 §4.1" |
| `scene_002_wind7_offscene` | 出行 | 航行/施工/高空作业/户外（不含出行） | 不输出 Beaufort/GB/T 28591 citation | 仍输出"GB/T 28591-2012 §4" |

> 桥接架构把这种"场景适配性"做进了 KB 的元数据，使得不同场景下的同一
> 数值能给出**不同的引用与建议**——这是 LLM 自由发挥所做不到的。

---

## 四、按用例类别拆分

| 类别 | 用例数 | rule_only · grade_id | rule_plus_rag · grade_id | **llm_baseline · grade_id** | llm · cite 真实 | rag · 引用率 |
|---|---:|---:|---:|---:|---:|---:|
| precipitation_24h | 11 | 100% | 100% | **0%** | 100% | 100% |
| precipitation_12h | 5 | 100% | 100% | **0%** | 100% | 100% |
| wind | 16 | 100% | 100% | **0%** | 100% | 100% |
| scene_filter | 2 | 100% | 100% | **0%** | 100% | — |
| multi | 2 | 100% | 100% | **0%** | 100% | 100% |
| fallback | 4 | 100% | 100% | **100%** | — | — |

> fallback 类别的 100% 来自 LLM **正确**判断"非法/无关字段不应输出 label"；
> 其余所有类别 grade_id = 0%，全部源于 LLM 凭印象编 ID 的命名风格与 KB
> 完全不一致。

---

## 五、论文写作可引用要点

### 5.1 论证 RAG 必要性的"双指标对比"

```
LLM 给 citation 出现率 100% ↔ 与 KB 严格一致命中率 42.4%
```

这一对数据足够独立成为论文 Q3 章节"为什么必须做 RAG"的核心论据：
**LLM 的 citation 在表面格式上几乎完美（100% 出现、100% 标准号真实），
但内核错误率高达 57.6%**——这种幻觉比"完全空白"更危险。

### 5.2 论证「双通路 RAG」中通路 B 的必要性

```
mode=rule_only  grade_id 准确率  100%
mode=llm_baseline grade_id 准确率  10%
```

把"35mm 该归大雨"的判定交给 LLM，每 10 条用例至少错 1.5 条 grade、
每 10 条全错 grade_id。但只要把"数值→分级"放进确定性规则表（rule_only），
就能 100% 正确。这是"通路 B（grade_id 硬链接）"的设计依据。

### 5.3 论证「场景元数据」的设计价值

```
mode=rule_plus_rag 场景过滤负例通过率 100%
mode=llm_baseline 场景过滤负例通过率 50%
```

LLM 倾向于在所有场景下都输出 citation，无法分辨"该说"与"不该说"。
桥接架构通过 KB 中 `applicable_scene` 显式建模场景适用性，使同一数值
在不同场景下给出不同回答——这是结构化知识库相对于 LLM 内部知识的
独有优势。

### 5.4 与「知识库标准核对表」的呼应

「知识库标准核对表-论文素材.md」中**人工核对**发现 12 项标准引用里
有 7 处错误（错引 / 张冠李戴 / 条款错位）；本实验中 LLM 自由发挥时
36/36 条非 fallback 用例的 citation **均存在不同程度的错误**，错误模式
**与人工核对发现的几乎一一对应**：

| 知识库人工核对发现的错误模式 | LLM baseline 复现 |
|---|---|
| JGJ 80 第 3.0.4 条 vs 真实 3.0.8 | LLM 在 4 次引用中给出 4 个不同的错条款号 |
| 寒潮误引 GB/T 20484（应为 GB/T 21987） | LLM 在 15 级风越界时混用蒲福风级 + GB/T 19201 热带气旋 |
| 蒲福 0 级 < 0.3 m/s 误差（应为 0.0–0.2） | LLM 给"清风"代替"清劲风"等用词不严格 |

这构成了一个**自洽的论证闭环**：
1. 人工核对种子数据 → 发现 LLM 类型的错误
2. LLM baseline 实验 → 同种错误以同样模式重新出现
3. 桥接架构通过 grade_id 硬链接 + 场景元数据 → 100% 避免上述错误

---

## 六、运行可重现性

```bash
# 三档（无网络，约 6 秒）
python -m experiments.eval.run_bridge_eval

# 四档（含 LLM 调用，约 7 分钟，第二次跑命中缓存约 30 秒）
python -m experiments.eval.run_bridge_eval --with-llm-baseline

# 强制重跑 LLM（不读缓存）
python -m experiments.eval.run_bridge_eval --with-llm-baseline --force-llm
```

实验结果以 (timestamp).json + .md 双格式落盘到 `experiments/results/`，
LLM 调用结果按 (input, scene, prompt_version, model) 摘要为 16 字符 sha256
键缓存到 `experiments/results/llm_baseline_cache.json`，重跑同一组合直接
命中，避免重复消耗 token。
