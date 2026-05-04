# 通路 A（RAG 检索）评测报告

- 评测时间：20260504_203504
- 用例总数：**60**
- 评测档位：vector, bm25, hybrid
- 每档返回 Top-K：5（统计 K=[1, 3, 5]）
- 评测集：`data/test_cases/rag_retrieval_bench.jsonl`

## 一、3 档检索器消融总表

| 指标 | mode=vector | mode=bm25 | mode=hybrid |
|---|---|---|---|
| Top-1 命中率（top1_hit_rate） | 0.817 | 0.633 | 0.850 |
| MRR（首个相关条目排名倒数） | 0.889 | 0.737 | 0.908 |
| Recall@1 | 71.9% | 56.1% | 75.3% |
| Recall@3 | 89.7% | 79.4% | 90.6% |
| Recall@5 | 97.8% | 85.8% | 96.9% |
| Precision@1 | 81.7% | 63.3% | 85.0% |
| Precision@3 | 35.6% | 31.7% | 35.6% |
| Precision@5 | 24.0% | 21.0% | 23.7% |
| Category@1（类别一致率） | 96.7% | 85.0% | 95.0% |
| Category@3（类别一致率） | 81.1% | 74.4% | 82.2% |
| Category@5（类别一致率） | 78.3% | 71.0% | 78.7% |

## 二、按用例类别拆分（Recall@5）

| 类别 | 用例数 | vector · Recall@5 | bm25 · Recall@5 | hybrid · Recall@5 |
|---|---|---|---|---|
| grade_humidity | 5 | 100.0% | 80.0% | 100.0% |
| grade_precip | 7 | 85.7% | 85.7% | 85.7% |
| grade_temp | 7 | 100.0% | 71.4% | 100.0% |
| grade_visibility | 6 | 100.0% | 75.0% | 100.0% |
| grade_wind | 7 | 100.0% | 100.0% | 100.0% |
| multi | 6 | 94.4% | 66.7% | 86.1% |
| op_agri | 1 | 100.0% | 100.0% | 100.0% |
| op_aviation | 1 | 100.0% | 100.0% | 100.0% |
| op_clothing | 1 | 100.0% | 100.0% | 100.0% |
| op_driving | 1 | 100.0% | 100.0% | 100.0% |
| op_high_altitude | 3 | 100.0% | 66.7% | 100.0% |
| op_life | 1 | 100.0% | 100.0% | 100.0% |
| op_outdoor | 2 | 100.0% | 100.0% | 100.0% |
| paraphrase | 4 | 100.0% | 100.0% | 100.0% |
| term | 8 | 100.0% | 100.0% | 100.0% |

## 三、按用例类别拆分（Top-1 命中率）

| 类别 | 用例数 | vector · top1 | bm25 · top1 | hybrid · top1 |
|---|---|---|---|---|
| grade_humidity | 5 | 100.0% | 60.0% | 80.0% |
| grade_precip | 7 | 71.4% | 42.9% | 71.4% |
| grade_temp | 7 | 71.4% | 57.1% | 71.4% |
| grade_visibility | 6 | 50.0% | 33.3% | 66.7% |
| grade_wind | 7 | 100.0% | 71.4% | 100.0% |
| multi | 6 | 83.3% | 83.3% | 83.3% |
| op_agri | 1 | 100.0% | 100.0% | 100.0% |
| op_aviation | 1 | 0.0% | 100.0% | 0.0% |
| op_clothing | 1 | 100.0% | 100.0% | 100.0% |
| op_driving | 1 | 100.0% | 100.0% | 100.0% |
| op_high_altitude | 3 | 100.0% | 33.3% | 100.0% |
| op_life | 1 | 100.0% | 100.0% | 100.0% |
| op_outdoor | 2 | 100.0% | 100.0% | 100.0% |
| paraphrase | 4 | 50.0% | 25.0% | 100.0% |
| term | 8 | 100.0% | 87.5% | 100.0% |

## 四、失败用例（top-1 未命中相关条目）

### mode=vector（11 条）

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

- **op_007_aviation_visibility** [op_aviation] 民航低能见度
  - query: `机场雾天会停飞吗？能见度多少米起飞？`
  - 期望相关 ids: `['op_aviation_low_visibility']`
  - 实际 top-5: `['grading_visibility_heavy_dense_fog', 'op_aviation_low_visibility', 'grading_visibility_fog', 'grading_visibility_dense_fog', 'grading_visibility_haze']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.200

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

- **grade_temp_003_cool** [grade_temp] 凉爽区间查询
  - query: `15度算什么气温？`
  - 期望相关 ids: `['grading_temperature_cool']`
  - 实际 top-5: `['grading_temperature_chilly', 'grading_temperature_cold', 'op_clothing_temperature', 'grading_temperature_cool', 'grading_temperature_warm']`
  - 指标：top1_hit=False, mrr=0.250, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=0.667, recall@5=1.000, precision@5=0.200, category@5=0.800

- **grade_temp_005_hot** [grade_temp] 炎热区间查询
  - query: `32度气温属于什么级别？`
  - 期望相关 ids: `['grading_temperature_hot']`
  - 实际 top-5: `['grading_temperature_warm', 'grading_temperature_hot', 'grading_temperature_comfortable', 'grading_temperature_cold', 'grading_temperature_chilly']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_vis_002_dense_fog** [grade_visibility] 浓雾区间查询
  - query: `能见度300米属于什么级别？`
  - 期望相关 ids: `['grading_visibility_dense_fog']`
  - 实际 top-5: `['grading_visibility_extreme', 'grading_visibility_dense_fog', 'grading_visibility_fog', 'grading_visibility_heavy_dense_fog', 'grading_visibility_excellent']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_vis_004_mist** [grade_visibility] 轻雾/轻霾区间查询
  - query: `能见度3公里属于轻雾还是浓雾？`
  - 期望相关 ids: `['grading_visibility_mist']`
  - 实际 top-5: `['grading_visibility_haze', 'grading_visibility_mist', 'grading_visibility_heavy_dense_fog', 'grading_visibility_extreme', 'grading_visibility_good']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_vis_005_fog_yellow** [grade_visibility] 大雾黄色预警阈值查询
  - query: `能见度500米属于雾还是浓雾？`
  - 期望相关 ids: `['grading_visibility_fog']`
  - 实际 top-5: `['grading_visibility_haze', 'grading_visibility_fog', 'grading_visibility_dense_fog', 'grading_visibility_heavy_dense_fog', 'grading_visibility_extreme']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

### mode=bm25（22 条）

- **term_002_thunderstorm** [term] 概念性问题：雷暴
  - query: `雷暴是什么？`
  - 期望相关 ids: `['term_thunderstorm']`
  - 实际 top-5: `['op_high_altitude_thunder', 'term_thunderstorm', 'op_outdoor_sport', 'grading_visibility_excellent', 'grading_precip_12h_rainstorm']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.200

- **grade_001_rain_heavy** [grade_precip] 24h 大雨阈值查询
  - query: `24小时降水量多少毫米算大雨？`
  - 期望相关 ids: `['grading_precip_24h_heavy']`
  - 实际 top-5: `['grading_precip_24h_light', 'grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_heavy', 'grading_precip_24h_heavy_rainstorm', 'grading_precip_24h_moderate']`
  - 指标：top1_hit=False, mrr=0.333, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_003_rain_rainstorm** [grade_precip] 24h 暴雨阈值查询
  - query: `24小时降水80毫米是暴雨吗？`
  - 期望相关 ids: `['grading_precip_24h_rainstorm']`
  - 实际 top-5: `['grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_rainstorm', 'grading_precip_24h_heavy_rainstorm', 'grading_precip_12h_rainstorm', 'grading_precip_24h_light']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_004_rain_heavy_rainstorm** [grade_precip] 24h 大暴雨阈值查询
  - query: `降水200毫米算什么级别？`
  - 期望相关 ids: `['grading_precip_24h_heavy_rainstorm']`
  - 实际 top-5: `['grading_visibility_dense_fog', 'grading_visibility_heavy_dense_fog', 'grading_precip_12h_light', 'grading_precip_12h_moderate', 'grading_precip_12h_heavy']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=1.000, recall@5=0.000, precision@5=0.000, category@5=1.000

- **grade_006_rain_12h_heavy** [grade_precip] 12h 大雨阈值查询
  - query: `12小时降水量25毫米算什么？`
  - 期望相关 ids: `['grading_precip_12h_heavy']`
  - 实际 top-5: `['grading_precip_12h_light', 'grading_precip_12h_moderate', 'grading_precip_12h_heavy', 'grading_precip_12h_rainstorm', 'grading_precip_24h_heavy']`
  - 指标：top1_hit=False, mrr=0.333, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_008_wind_5** [grade_wind] 5 级风查询（清劲风）
  - query: `5 级风是什么风？`
  - 期望相关 ids: `['grading_wind_beaufort_5']`
  - 实际 top-5: `['grading_wind_beaufort_1', 'grading_wind_beaufort_5', 'grading_wind_beaufort_4', 'term_typhoon', 'grading_wind_beaufort_3']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=0.800

- **grade_014_wind_strong_name** [grade_wind] 按风级中文名反查
  - query: `强风是几级风？`
  - 期望相关 ids: `['grading_wind_beaufort_6']`
  - 实际 top-5: `['term_typhoon', 'grading_wind_beaufort_6', 'grading_humidity_extreme', 'grading_temperature_cool', 'op_high_altitude_wind']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.667, recall@5=1.000, precision@5=0.200, category@5=0.600

- **grade_016_visibility_fog** [grade_visibility] 能见度等级
  - query: `什么算大雾？能见度低于多少米？`
  - 期望相关 ids: `['grading_visibility_haze']`
  - 实际 top-5: `['op_aviation_low_visibility', 'grading_visibility_fog', 'grading_visibility_heavy_dense_fog', 'grading_visibility_dense_fog', 'grading_visibility_haze']`
  - 指标：top1_hit=False, mrr=0.200, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.667, recall@5=1.000, precision@5=0.200, category@5=0.800

- **op_001_high_altitude_wind** [op_high_altitude] 高空作业风力强制停止
  - query: `几级风必须停止高空作业？`
  - 期望相关 ids: `['op_high_altitude_wind']`
  - 实际 top-5: `['grading_wind_beaufort_8', 'grading_wind_beaufort_9', 'grading_visibility_heavy_dense_fog', 'grading_wind_beaufort_7', 'op_high_altitude_visibility']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.000, recall@5=0.000, precision@5=0.000, category@5=0.200

- **op_003_high_altitude_visibility** [op_high_altitude] 高空作业能见度限制
  - query: `雾天可以高空作业吗？`
  - 期望相关 ids: `['op_high_altitude_visibility']`
  - 实际 top-5: `['op_high_altitude_thunder', 'op_high_altitude_visibility', 'grading_visibility_extreme', 'op_high_altitude_wind', 'grading_visibility_heavy_dense_fog']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=0.667, recall@5=1.000, precision@5=0.200, category@5=0.600

- **multi_002_rainstorm** [multi] 暴雨同时跨等级 + 驾驶建议
  - query: `暴雨怎么应对？`
  - 期望相关 ids: `['grading_precip_24h_rainstorm', 'op_driving_rain']`
  - 实际 top-5: `['term_thunderstorm', 'grading_precip_12h_rainstorm', 'op_outdoor_sport', 'grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_heavy_rainstorm']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.667, recall@5=0.000, precision@5=0.000, category@5=0.800

- **para_002_colloquial_wind** [paraphrase] 口语化：'刮大风' 应能召回 6-8 级
  - query: `今天刮大风，多大算大风？`
  - 期望相关 ids: `['grading_wind_beaufort_8']`
  - 实际 top-5: `['op_driving_rain', 'term_apparent_temperature', 'grading_wind_beaufort_12', 'grading_wind_beaufort_10', 'grading_wind_beaufort_8']`
  - 指标：top1_hit=False, mrr=0.200, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.600

- **para_003_synonym_fog** [paraphrase] 同义改写：'起雾'
  - query: `今天早晨起雾很厉害，能见度低于多少算大雾？`
  - 期望相关 ids: `['grading_visibility_haze', 'grading_visibility_fog']`
  - 实际 top-5: `['op_aviation_low_visibility', 'grading_visibility_extreme', 'grading_visibility_fog', 'grading_visibility_haze', 'op_high_altitude_visibility']`
  - 指标：top1_hit=False, mrr=0.333, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.500, precision@3=0.333, category@3=0.667, recall@5=1.000, precision@5=0.400, category@5=0.600

- **grade_temp_003_cool** [grade_temp] 凉爽区间查询
  - query: `15度算什么气温？`
  - 期望相关 ids: `['grading_temperature_cool']`
  - 实际 top-5: `['op_clothing_temperature', 'grading_temperature_high_warning', 'term_apparent_temperature', 'grading_precip_12h_heavy', 'op_outdoor_high_temp']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.333, recall@5=0.000, precision@5=0.000, category@5=0.400

- **grade_temp_004_warm** [grade_temp] 温暖区间查询
  - query: `28度算暖和还是热？`
  - 期望相关 ids: `['grading_temperature_warm']`
  - 实际 top-5: `['grading_temperature_comfortable', 'grading_temperature_warm', 'term_cold_wave', 'grading_humidity_extreme', 'grading_visibility_excellent']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=0.667, recall@5=1.000, precision@5=0.200, category@5=0.800

- **grade_temp_005_hot** [grade_temp] 炎热区间查询
  - query: `32度气温属于什么级别？`
  - 期望相关 ids: `['grading_temperature_hot']`
  - 实际 top-5: `['grading_wind_beaufort_12', 'grading_temperature_high_warning', 'grading_humidity_very_dry', 'grading_temperature_cold', 'grading_visibility_extreme']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=1.000, recall@5=0.000, precision@5=0.000, category@5=1.000

- **grade_vis_002_dense_fog** [grade_visibility] 浓雾区间查询
  - query: `能见度300米属于什么级别？`
  - 期望相关 ids: `['grading_visibility_dense_fog']`
  - 实际 top-5: `['grading_visibility_extreme', 'grading_visibility_mist', 'grading_visibility_haze', 'op_aviation_low_visibility', 'grading_wind_beaufort_12']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=1.000, recall@5=0.000, precision@5=0.000, category@5=0.800

- **grade_vis_003_heavy_dense** [grade_visibility] 强浓雾红色预警查询
  - query: `大雾红色预警的能见度阈值是多少？`
  - 期望相关 ids: `['grading_visibility_heavy_dense_fog', 'grading_visibility_extreme']`
  - 实际 top-5: `['grading_visibility_haze', 'grading_visibility_heavy_dense_fog', 'grading_visibility_dense_fog', 'grading_temperature_high_warning', 'grading_visibility_fog']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.500, precision@3=0.333, category@3=1.000, recall@5=0.500, precision@5=0.200, category@5=1.000

- **grade_vis_005_fog_yellow** [grade_visibility] 大雾黄色预警阈值查询
  - query: `能见度500米属于雾还是浓雾？`
  - 期望相关 ids: `['grading_visibility_fog']`
  - 实际 top-5: `['grading_visibility_dense_fog', 'grading_visibility_haze', 'grading_visibility_fog', 'grading_visibility_heavy_dense_fog', 'grading_visibility_extreme']`
  - 指标：top1_hit=False, mrr=0.333, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_hum_003_extreme** [grade_humidity] 极潮湿查询
  - query: `相对湿度95%属于什么级别？`
  - 期望相关 ids: `['grading_humidity_extreme']`
  - 实际 top-5: `['grading_humidity_very_dry', 'grading_humidity_comfort', 'grading_humidity_dry', 'grading_humidity_humid', 'grading_humidity_very_humid']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=1.000, recall@5=0.000, precision@5=0.000, category@5=1.000

- **grade_hum_004_very_dry** [grade_humidity] 极干燥查询
  - query: `湿度只有20%是不是太干了？`
  - 期望相关 ids: `['grading_humidity_very_dry']`
  - 实际 top-5: `['grading_humidity_dry', 'grading_humidity_very_dry', 'grading_visibility_excellent', 'grading_humidity_comfort', 'grading_visibility_mist']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **para_004_synonym_humid** [paraphrase] 同义改写：'闷热'
  - query: `今天又闷又湿，湿度多少算闷？`
  - 期望相关 ids: `['grading_humidity_humid', 'grading_humidity_very_humid']`
  - 实际 top-5: `['term_dew_point', 'grading_humidity_very_humid', 'grading_humidity_comfort', 'term_apparent_temperature', 'grading_humidity_humid']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.500, precision@3=0.333, category@3=0.667, recall@5=1.000, precision@5=0.400, category@5=0.600

### mode=hybrid（9 条）

- **grade_004_rain_heavy_rainstorm** [grade_precip] 24h 大暴雨阈值查询
  - query: `降水200毫米算什么级别？`
  - 期望相关 ids: `['grading_precip_24h_heavy_rainstorm']`
  - 实际 top-5: `['grading_precip_24h_extreme_rainstorm', 'grading_precip_24h_light', 'grading_precip_24h_rainstorm', 'grading_precip_12h_light', 'grading_precip_24h_moderate']`
  - 指标：top1_hit=False, mrr=0.000, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=0.000, precision@3=0.000, category@3=1.000, recall@5=0.000, precision@5=0.000, category@5=1.000

- **grade_006_rain_12h_heavy** [grade_precip] 12h 大雨阈值查询
  - query: `12小时降水量25毫米算什么？`
  - 期望相关 ids: `['grading_precip_12h_heavy']`
  - 实际 top-5: `['grading_precip_12h_rainstorm', 'grading_precip_12h_heavy', 'grading_precip_12h_moderate', 'grading_precip_12h_light', 'grading_precip_24h_heavy']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **op_007_aviation_visibility** [op_aviation] 民航低能见度
  - query: `机场雾天会停飞吗？能见度多少米起飞？`
  - 期望相关 ids: `['op_aviation_low_visibility']`
  - 实际 top-5: `['grading_visibility_heavy_dense_fog', 'op_aviation_low_visibility', 'grading_visibility_fog', 'grading_visibility_dense_fog', 'grading_visibility_haze']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=1.000, precision@3=0.333, category@3=0.333, recall@5=1.000, precision@5=0.200, category@5=0.200

- **multi_002_rainstorm** [multi] 暴雨同时跨等级 + 驾驶建议
  - query: `暴雨怎么应对？`
  - 期望相关 ids: `['grading_precip_24h_rainstorm', 'op_driving_rain']`
  - 实际 top-5: `['term_thunderstorm', 'grading_precip_24h_heavy_rainstorm', 'grading_precip_24h_extreme_rainstorm', 'op_driving_rain', 'grading_precip_12h_rainstorm']`
  - 指标：top1_hit=False, mrr=0.250, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.667, recall@5=0.500, precision@5=0.200, category@5=0.800

- **grade_temp_003_cool** [grade_temp] 凉爽区间查询
  - query: `15度算什么气温？`
  - 期望相关 ids: `['grading_temperature_cool']`
  - 实际 top-5: `['op_clothing_temperature', 'grading_temperature_chilly', 'grading_temperature_cold', 'grading_temperature_warm', 'grading_temperature_cool']`
  - 指标：top1_hit=False, mrr=0.200, recall@1=0.000, precision@1=0.000, category@1=0.000, recall@3=0.000, precision@3=0.000, category@3=0.667, recall@5=1.000, precision@5=0.200, category@5=0.800

- **grade_temp_005_hot** [grade_temp] 炎热区间查询
  - query: `32度气温属于什么级别？`
  - 期望相关 ids: `['grading_temperature_hot']`
  - 实际 top-5: `['grading_temperature_warm', 'grading_temperature_hot', 'grading_temperature_cold', 'grading_temperature_high_warning', 'grading_temperature_chilly']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_vis_002_dense_fog** [grade_visibility] 浓雾区间查询
  - query: `能见度300米属于什么级别？`
  - 期望相关 ids: `['grading_visibility_dense_fog']`
  - 实际 top-5: `['grading_visibility_extreme', 'grading_visibility_dense_fog', 'grading_visibility_fog', 'grading_visibility_heavy_dense_fog', 'grading_visibility_haze']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_vis_005_fog_yellow** [grade_visibility] 大雾黄色预警阈值查询
  - query: `能见度500米属于雾还是浓雾？`
  - 期望相关 ids: `['grading_visibility_fog']`
  - 实际 top-5: `['grading_visibility_haze', 'grading_visibility_fog', 'grading_visibility_dense_fog', 'grading_visibility_heavy_dense_fog', 'grading_visibility_extreme']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

- **grade_hum_004_very_dry** [grade_humidity] 极干燥查询
  - query: `湿度只有20%是不是太干了？`
  - 期望相关 ids: `['grading_humidity_very_dry']`
  - 实际 top-5: `['grading_humidity_dry', 'grading_humidity_very_dry', 'grading_humidity_comfort', 'grading_humidity_humid', 'grading_humidity_very_humid']`
  - 指标：top1_hit=False, mrr=0.500, recall@1=0.000, precision@1=0.000, category@1=1.000, recall@3=1.000, precision@3=0.333, category@3=1.000, recall@5=1.000, precision@5=0.200, category@5=1.000

## 五、关键结论（自动摘要）

- **混合检索的边际增益**：Recall@5 上 hybrid=96.9% vs vector=97.8% / bm25=85.8%；MRR 上 hybrid=0.908 vs vector=0.889 / bm25=0.737。
- **Top-1 命中率**：hybrid=85.0% vs vector=81.7% / bm25=63.3%，反映实际作为 LLM 上下文最重要的「第一引用项」准确度。
