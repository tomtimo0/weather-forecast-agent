# 意图识别 + 参数补全评测报告

- 评测时间：20260504_220810
- 用例总数：**35**
- 模型：Pro/zai-org/GLM-5.1
- 评测集：`data/test_cases/intent_bench.jsonl`
- 评测脚本：`experiments/eval/run_intent_eval.py`

## 一、总表

| 指标 | 数值 |
|---|---:|
| 端到端通过率 | **91.4%** |
| 意图准确率 | 97.1% |
| 地点召回率 | 96.6% |
| 地点精确率 | 95.6% |
| 地点角色准确率 | 100.0% |
| 时间字段识别率 | 91.7% |
| 补全判定准确率 | 100.0% |
| 追问触发准确率 | 100.0% |
| 补全字段覆盖率 | 50.0% |

## 二、按用例类别拆分

| 类别 | 用例数 | 端到端 | 意图 | 地点召回 | 地点角色 | 时间字段 | 补全判定 | 追问 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| adversarial | 2 | 100.0% | 100.0% | — | — | — | 100.0% | 100.0% |
| context_inference | 3 | 33.3% | 66.7% | 50.0% | 100.0% | 33.3% | 100.0% | 100.0% |
| current_weather | 4 | 100.0% | 100.0% | 100.0% | 100.0% | — | 100.0% | 100.0% |
| daily_forecast | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| historical_daily | 2 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| historical_hourly | 2 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| hourly_forecast | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| life_index | 4 | 75.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| travel_advice | 5 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| weather_warning | 3 | 100.0% | 100.0% | 100.0% | 100.0% | — | 100.0% | 100.0% |

## 三、失败用例（3 条）

### index_004_no_loc [life_index]

- query: `今天去爬山合适吗？`
- ❌ 地点错增：期望空，实际识别 ['当前位置']
- 实际意图: `life_index` | 地点: `[('当前位置', 'target')]` | 时间: `{'raw_text': None, 'date': '今天', 'start_time': None, 'end_time': None}`
- 补全: is_complete=False，follow_up=您想查询哪个城市的生活指数？请告诉我您所在的城市名称。，notes=['time.date']

### ctx_002_switch_loc [context_inference]

- query: `那成都呢？`
- context: `上一轮：用户问『查一下北京明天的天气』，助手回答了北京明天的预报。`
- ❌ 意图错误：期望 {'daily_forecast'}，实际 current_weather
- ❌ 时间字段缺失：期望 ['date']，缺 ['date']
- ❌ 补全字段未覆盖：缺 ['time.date']，notes 实际 []
- 实际意图: `current_weather` | 地点: `[('成都', 'target')]` | 时间: `None`
- 补全: is_complete=True，follow_up=无，notes=[]

### ctx_003_switch_intent [context_inference]

- query: `那需要防晒吗？`
- context: `上一轮：用户问『武汉明天天气』，助手回答了武汉明天的预报。`
- ❌ 地点漏识别：缺少 [['wuhan', '武汉']]
- ❌ 时间字段缺失：期望 ['date']，缺 ['date']
- ❌ 补全字段未覆盖：缺 ['locations', 'time.date']，notes 实际 []
- 实际意图: `life_index` | 地点: `[]` | 时间: `None`
- 补全: is_complete=True，follow_up=无，notes=[]
