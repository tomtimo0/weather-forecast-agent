# 通路 A（RAG 检索）评测报告

- 评测时间：20260504_200940
- 用例总数：**43**
- 评测档位：vector, bm25, hybrid
- 每档返回 Top-K：5（统计 K=[1, 3, 5]）
- 评测集：`data/test_cases/rag_retrieval_bench.jsonl`

## 一、3 档检索器消融总表

| 指标 | mode=vector | mode=bm25 | mode=hybrid |
|---|---|---|---|
| Top-1 命中率（top1_hit_rate） | 0.884 | 0.674 | 0.907 |
| MRR（首个相关条目排名倒数） | 0.921 | 0.778 | 0.936 |
| Recall@1 | 82.2% | 61.2% | 84.5% |
| Recall@3 | 91.9% | 84.9% | 93.0% |
| Recall@5 | 97.7% | 91.9% | 97.7% |
| Precision@1 | 88.4% | 67.4% | 90.7% |
| Precision@3 | 34.9% | 31.8% | 34.9% |
| Precision@5 | 22.8% | 20.9% | 22.8% |
| Category@1（类别一致率） | 97.7% | 81.4% | 95.3% |
| Category@3（类别一致率） | 76.7% | 69.8% | 76.7% |
| Category@5（类别一致率） | 73.0% | 65.6% | 71.2% |

## 二、按用例类别拆分（Recall@5）

| 类别 | 用例数 | vector · Recall@5 | bm25 · Recall@5 | hybrid · Recall@5 |
|---|---|---|---|---|
| grade_humidity | 1 | 100.0% | 100.0% | 100.0% |
| grade_precip | 7 | 85.7% | 85.7% | 85.7% |
| grade_temp | 1 | 100.0% | 100.0% | 100.0% |
| grade_visibility | 1 | 100.0% | 100.0% | 100.0% |
| grade_wind | 7 | 100.0% | 100.0% | 100.0% |
| multi | 5 | 100.0% | 70.0% | 100.0% |
| op_agri | 1 | 100.0% | 100.0% | 100.0% |
| op_aviation | 1 | 100.0% | 100.0% | 100.0% |
| op_clothing | 1 | 100.0% | 100.0% | 100.0% |
| op_driving | 1 | 100.0% | 100.0% | 100.0% |
| op_high_altitude | 3 | 100.0% | 100.0% | 100.0% |
| op_life | 1 | 100.0% | 100.0% | 100.0% |
| op_outdoor | 2 | 100.0% | 100.0% | 100.0% |
| paraphrase | 3 | 100.0% | 66.7% | 100.0% |
| term | 8 | 100.0% | 100.0% | 100.0% |

## 三、按用例类别拆分（Top-1 命中率）

| 类别 | 用例数 | vector · top1 | bm25 · top1 | hybrid · top1 |
|---|---|---|---|---|
| grade_humidity | 1 | 100.0% | 100.0% | 100.0% |
| grade_precip | 7 | 71.4% | 42.9% | 71.4% |
| grade_temp | 1 | 100.0% | 100.0% | 100.0% |
| grade_visibility | 1 | 100.0% | 0.0% | 100.0% |
| grade_wind | 7 | 100.0% | 71.4% | 85.7% |
| multi | 5 | 80.0% | 80.0% | 80.0% |
| op_agri | 1 | 100.0% | 100.0% | 100.0% |
| op_aviation | 1 | 100.0% | 100.0% | 100.0% |
| op_clothing | 1 | 100.0% | 100.0% | 100.0% |
| op_driving | 1 | 100.0% | 100.0% | 100.0% |
| op_high_altitude | 3 | 100.0% | 33.3% | 100.0% |
| op_life | 1 | 100.0% | 100.0% | 100.0% |
| op_outdoor | 2 | 100.0% | 100.0% | 100.0% |
| paraphrase | 3 | 33.3% | 0.0% | 100.0% |
| term | 8 | 100.0% | 87.5% | 100.0% |

## 四、失败用例（top-1 未命中相关条目）

### mode=vector（5 条）

- **grade_004_rain_heavy_rainstorm** [grade_precip] 24h 大暴雨阈值查询
  - query: `降水200毫米算什么级别？`
  - 期望相关 ids: `['grading_precip_24h_heavy_rainstorm']`
  - 实际 top-5: `['grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_light', 'grading_precip_24h_rainstorm', 'grading_precip_24h_moderate', 'grading_precip_12h_light']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=1.000, recall@5=0.000, precision@5=0.000, category@5=1.000

- **grade_006_rain_12h_heavy** [grade_precip] 12h 大雨阈值查询
  - query: `12小时降水量25毫米算什么？`
  - 期望相关 ids: `['grading_precip_12h_heavy']`
  - 实际 top-5: `['grading_precip_24h_extreme_rainstorm', 'grading_precip_12h_rainstorm', 'grading_precip_24h_rainstorm', 'grading_precip_12h_heavy', 'grading_precip_12h_moderate']`
  - 指标：top1_hit=False, mrr=0.250, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **multi_002_rainstorm** [multi] 暴雨同时跨等级 + 驾驶建议
  - query: `暴雨怎么应对？`
  - 期望相关 ids: `['grading_precip_24h_rainstorm', 'op_driving_rain']`
  - 实际 top-5: `['term_thunderstorm', 'grading_precip_24h_heavy_rainstorm', 'op_driving_rain', 'grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_rainstorm']`
  - 指标：top1_hit=False, mrr=0.333, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.500, precision@3=0.333, category@3=0.667, recall@5=1.000, precision@5=0.400, category@5=0.800

- **para_001_synonym_rain** [paraphrase] 同义改写：'下大雨' 应仍能召回大雨条目
  - query: `下了一天大雨，量是多少？`
  - 期望相关 ids: `['grading_precip_24h_heavy']`
  - 实际 top-5: `['grading_precip_12h_heavy', 'grading_precip_24h_heavy', 'grading_precip_24h_heavy_rainstorm', 'grading_precip_12h_rainstorm', 'grading_precip_24h_rainstorm']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **para_002_colloquial_wind** [paraphrase] 口语化：'刮大风' 应能召回 6-8 级
  - query: `今天刮大风，多大算大风？`
  - 期望相关 ids: `['grading_wind_beaufort_8']`
  - 实际 top-5: `['grading_wind_beaufort_6', 'grading_wind_beaufort_8', 'grading_wind_beaufort_10', 'grading_wind_beaufort_4', 'grading_wind_beaufort_3']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

### mode=bm25（14 条）

- **term_002_thunderstorm** [term] 概念性问题：雷暴
  - query: `雷暴是什么？`
  - 期望相关 ids: `['term_thunderstorm']`
  - 实际 top-5: `['op_high_altitude_thunder', 'term_thunderstorm', 'op_outdoor_sport', 'grading_temperature_high_warning', 'grading_precip_12h_rainstorm']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.200

- **grade_001_rain_heavy** [grade_precip] 24h 大雨阈值查询
  - query: `24小时降水量多少毫米算大雨？`
  - 期望相关 ids: `['grading_precip_24h_heavy']`
  - 实际 top-5: `['grading_precip_24h_light', 'grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_heavy', 'grading_precip_24h_heavy_rainstorm', 'grading_precip_24h_moderate']`
  - 指标：top1_hit=False, mrr=0.333, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_003_rain_rainstorm** [grade_precip] 24h 暴雨阈值查询
  - query: `24小时降水80毫米是暴雨吗？`
  - 期望相关 ids: `['grading_precip_24h_rainstorm']`
  - 实际 top-5: `['grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_rainstorm', 'grading_precip_24h_heavy_rainstorm', 'grading_precip_12h_rainstorm', 'grading_precip_24h_moderate']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_004_rain_heavy_rainstorm** [grade_precip] 24h 大暴雨阈值查询
  - query: `降水200毫米算什么级别？`
  - 期望相关 ids: `['grading_precip_24h_heavy_rainstorm']`
  - 实际 top-5: `['grading_wind_beaufort_12', 'grading_visibility_haze', 'op_carwash', 'grading_precip_12h_light', 'grading_precip_12h_moderate']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=0.667, recall@5=0.000, precision@5=0.000, category@5=0.800

- **grade_006_rain_12h_heavy** [grade_precip] 12h 大雨阈值查询
  - query: `12小时降水量25毫米算什么？`
  - 期望相关 ids: `['grading_precip_12h_heavy']`
  - 实际 top-5: `['grading_precip_12h_light', 'grading_precip_12h_moderate', 'grading_precip_12h_heavy', 'grading_precip_12h_rainstorm', 'grading_precip_24h_heavy']`
  - 指标：top1_hit=False, mrr=0.333, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_008_wind_5** [grade_wind] 5 级风查询（清劲风）
  - query: `5 级风是什么风？`
  - 期望相关 ids: `['grading_wind_beaufort_5']`
  - 实际 top-5: `['grading_temperature_high_warning', 'grading_wind_beaufort_1', 'grading_wind_beaufort_5', 'grading_wind_beaufort_4', 'term_typhoon']`
  - 指标：top1_hit=False, mrr=0.333, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=0.800

- **grade_014_wind_strong_name** [grade_wind] 按风级中文名反查
  - query: `强风是几级风？`
  - 期望相关 ids: `['grading_wind_beaufort_6']`
  - 实际 top-5: `['term_drizzle', 'term_typhoon', 'grading_temperature_high_warning', 'grading_wind_beaufort_6', 'op_high_altitude_wind']`
  - 指标：top1_hit=False, mrr=0.250, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.400

- **grade_016_visibility_fog** [grade_visibility] 能见度等级
  - query: `什么算大雾？能见度低于多少米？`
  - 期望相关 ids: `['grading_visibility_haze']`
  - 实际 top-5: `['op_aviation_low_visibility', 'grading_visibility_haze', 'op_high_altitude_visibility', 'term_drizzle', 'op_driving_rain']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.200

- **op_001_high_altitude_wind** [op_high_altitude] 高空作业风力强制停止
  - query: `几级风必须停止高空作业？`
  - 期望相关 ids: `['op_high_altitude_wind']`
  - 实际 top-5: `['grading_wind_beaufort_8', 'grading_wind_beaufort_9', 'op_high_altitude_visibility', 'op_high_altitude_thunder', 'op_high_altitude_wind']`
  - 指标：top1_hit=False, mrr=0.200, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.600

- **op_003_high_altitude_visibility** [op_high_altitude] 高空作业能见度限制
  - query: `雾天可以高空作业吗？`
  - 期望相关 ids: `['op_high_altitude_visibility']`
  - 实际 top-5: `['op_high_altitude_thunder', 'op_high_altitude_visibility', 'op_high_altitude_wind', 'op_outdoor_high_temp', 'grading_visibility_haze']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=0.800

- **multi_002_rainstorm** [multi] 暴雨同时跨等级 + 驾驶建议
  - query: `暴雨怎么应对？`
  - 期望相关 ids: `['grading_precip_24h_rainstorm', 'op_driving_rain']`
  - 实际 top-5: `['term_thunderstorm', 'op_outdoor_sport', 'grading_visibility_haze', 'op_high_altitude_wind', 'grading_precip_24h_heavy_rainstorm']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.667, recall@5=0.000, precision@5=0.000, category@5=0.800

- **para_001_synonym_rain** [paraphrase] 同义改写：'下大雨' 应仍能召回大雨条目
  - query: `下了一天大雨，量是多少？`
  - 期望相关 ids: `['grading_precip_24h_heavy']`
  - 实际 top-5: `['term_dew_point', 'grading_precip_24h_heavy', 'term_thunderstorm', 'op_driving_rain', 'grading_precip_24h_light']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.400

- **para_002_colloquial_wind** [paraphrase] 口语化：'刮大风' 应能召回 6-8 级
  - query: `今天刮大风，多大算大风？`
  - 期望相关 ids: `['grading_wind_beaufort_8']`
  - 实际 top-5: `['op_driving_rain', 'term_apparent_temperature', 'grading_wind_beaufort_12', 'op_aviation_low_visibility', 'term_thunderstorm']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.333, recall@5=0.000, precision@5=0.000, category@5=0.200

- **para_003_synonym_fog** [paraphrase] 同义改写：'起雾'
  - query: `今天早晨起雾很厉害，能见度低于多少算大雾？`
  - 期望相关 ids: `['grading_visibility_haze']`
  - 实际 top-5: `['op_aviation_low_visibility', 'grading_visibility_haze', 'op_high_altitude_visibility', 'op_driving_rain', 'term_drizzle']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.200

### mode=hybrid（4 条）

- **grade_004_rain_heavy_rainstorm** [grade_precip] 24h 大暴雨阈值查询
  - query: `降水200毫米算什么级别？`
  - 期望相关 ids: `['grading_precip_24h_heavy_rainstorm']`
  - 实际 top-5: `['grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_light', 'grading_precip_12h_light', 'grading_precip_12h_moderate', 'grading_precip_24h_rainstorm']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=1.000, recall@5=0.000, precision@5=0.000, category@5=1.000

- **grade_006_rain_12h_heavy** [grade_precip] 12h 大雨阈值查询
  - query: `12小时降水量25毫米算什么？`
  - 期望相关 ids: `['grading_precip_12h_heavy']`
  - 实际 top-5: `['grading_precip_12h_rainstorm', 'grading_precip_12h_heavy', 'grading_precip_12h_moderate', 'grading_precip_12h_light', 'grading_precip_24h_heavy']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_014_wind_strong_name** [grade_wind] 按风级中文名反查
  - query: `强风是几级风？`
  - 期望相关 ids: `['grading_wind_beaufort_6']`
  - 实际 top-5: `['term_typhoon', 'grading_wind_beaufort_6', 'op_high_altitude_wind', 'grading_wind_beaufort_12', 'grading_wind_beaufort_5']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.600

- **multi_002_rainstorm** [multi] 暴雨同时跨等级 + 驾驶建议
  - query: `暴雨怎么应对？`
  - 期望相关 ids: `['grading_precip_24h_rainstorm', 'op_driving_rain']`
  - 实际 top-5: `['term_thunderstorm', 'grading_precip_24h_heavy_rainstorm', 'grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_rainstorm', 'op_driving_rain']`
  - 指标：top1_hit=False, mrr=0.250, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.667, recall@5=1.000, precision@5=0.400, category@5=0.800

## 五、关键结论（自动摘要）

- **混合检索的边际增益**：Recall@5 上 hybrid=97.7% vs vector=97.7% / bm25=91.9%；MRR 上 hybrid=0.936 vs vector=0.921 / bm25=0.778。
- **Top-1 命中率**：hybrid=90.7% vs vector=88.4% / bm25=67.4%，反映实际作为 LLM 上下文最重要的「第一引用项」准确度。
- 结论：混合检索在 Recall 上不弱于任一单路，且通常优于纯向量（处理「清劲风/疾风」等专有名词时 BM25 路径补足）或纯 BM25（处理「打雷怎么应对」等同义改写时向量路径补足），支持论文中混合检索的设计选择。
