# 代码生成 + 执行 vs LLM 自由直算 评测报告

- 评测时间：20260504_230656
- 用例总数：**18**
- 评测档位：oracle, llm_direct, llm_with_code
- 模型：Pro/zai-org/GLM-5.1
- 评测集：`data/test_cases/code_exec_bench.jsonl`
- 评测脚本：`experiments/eval/run_code_eval.py`

## 一、3 档消融总表

| 指标 | oracle | llm_direct | llm_with_code |
|---|:---:|:---:|:---:|
| 数值准确率（核心） | 100.0% | 66.7% | 88.9% |
| 代码生成率 | — | — | 94.4% |
| 代码可执行率 | — | — | 94.4% |

## 二、按用例类别拆分（数值准确率）

| 类别 | 用例数 | oracle | llm_direct | llm_with_code |
|---|:---:|:---:|:---:|:---:|
| average | 5 | 100.0% | 80.0% | 100.0% |
| count | 2 | 100.0% | 50.0% | 100.0% |
| diff | 4 | 100.0% | 75.0% | 75.0% |
| extreme | 3 | 100.0% | 0.0% | 66.7% |
| sort | 2 | 100.0% | 100.0% | 100.0% |
| sum | 2 | 100.0% | 100.0% | 100.0% |

## 三、失败用例（仅展示 llm_direct / llm_with_code）

### mode=llm_direct（6 条失败）

- **avg_005_feels_like** [average]
  - 期望：`24.9`（type=scalar）
  - 实际：`25.0`
  - reasoning: 8个小时的体感温度之和为21.5+24.2+27.8+29.6+28.3+25.1+22.7+20.4=199.6，平均为199.6/8=24.95，保留1位小数为25.0

- **extreme_001_hottest_day** [extreme]
  - 期望：`{'date': '2025-07-03', 'tempMax': 36.8}`（type=date_with_value）
  - 实际：`2025-07-03`
  - reasoning: 7天中2025-07-03的最高温36.8°C为最大值

- **extreme_002_max_precip_day** [extreme]
  - 期望：`{'date': '2025-06-19', 'precip': 61.3}`（type=date_with_value）
  - 实际：`2025-06-19`
  - reasoning: 7天中2025-06-19的降水量61.3mm为最大值

- **extreme_003_coldest_hour** [extreme]
  - 期望：`{'time': '03:00', 'temp': -19.3}`（type=time_with_value）
  - 实际：`03:00`
  - reasoning: 在昨晚到今晨的逐小时气温中，03:00的气温最低，为-19.3°C。

- **diff_001_max_diurnal** [diff]
  - 期望：`{'date': '2025-09-18', 'tempDiff': 22.7}`（type=date_with_value）
  - 实际：`2025-09-18`
  - reasoning: 计算每日日较差：15.6, 18.9, 10.4, 22.7, 13.3, 14.3, 8.4，最大值为22.7°C，出现在9月18日

- **count_001_rainy_days** [count]
  - 期望：`7`（type=scalar）
  - 实际：`6`
  - reasoning: 在14天数据中，降水量>0的天数为6天：4月2日(2.3)、3日(0.5)、5日(15.8)、8日(4.7)、9日(12.4)、12日(1.8)、14日(3.2)

### mode=llm_with_code（2 条失败）

- **extreme_001_hottest_day** [extreme]
  - 期望：`{'date': '2025-07-03', 'tempMax': 36.8}`（type=date_with_value）
  - 实际：`None`
  - 代码生成失败
  - reasoning: 代码生成失败：LLM 未触发结构化输出

- **diff_001_max_diurnal** [diff]
  - 期望：`{'date': '2025-09-18', 'tempDiff': 22.7}`（type=date_with_value）
  - 实际：`{'date': '2025-09-18', 'range': 22.7}`
  - 代码执行成功但结果错误（潜在算法 bug）
  - reasoning: 遍历每日数据，计算日较差（tempMax - tempMin），记录最大值及其对应日期，返回日期和日较差。
  - code:
```python
def compute(data):
    daily = data["daily"]
    max_range = -1
    max_date = None
    for day in daily:
        diff = day["tempMax"] - day["tempMin"]
        if diff > max_range:
            max_range = diff
            max_date = day["date"]
    return {"date": max_date, "range": round(max_range, 1)}

```
