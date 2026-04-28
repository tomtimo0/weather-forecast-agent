"""意图识别模块测试

涵盖 8 类典型气象查询场景，运行时打印识别结果，便于人工核验。
"""

from src.intent.recognizer import recognize_intent


# 典型测试用例：(用户问题, 期望意图类型)
TEST_CASES = [
    ("武汉现在天气怎么样？", "current_weather"),
    ("北京明天早上8点天气如何？", "hourly_forecast"),
    ("成都未来三天的天气怎么样？", "daily_forecast"),
    ("上海有没有天气预警？", "weather_warning"),
    ("明天广州适合洗车吗？", "life_index"),
    ("去年12月25日深圳的逐小时气温是多少？", "historical_hourly"),
    ("2024年8月武汉每天的最高温是多少？", "historical_daily"),
    ("明天早八到晚六，从成都坐高铁到武汉，有什么穿衣建议？", "travel_advice"),
]


def run_tests():
    """运行所有测试用例并打印对比结果。"""
    print("=" * 80)
    print("意图识别模块测试")
    print("=" * 80)

    pass_count = 0
    for i, (query, expected_intent) in enumerate(TEST_CASES, 1):
        print(f"\n【测试 {i}】用户问题：{query}")
        print(f"  期望意图：{expected_intent}")

        try:
            intent = recognize_intent(query)
            actual_intent = intent.intent
            is_pass = actual_intent == expected_intent
            if is_pass:
                pass_count += 1

            status = "PASS" if is_pass else "FAIL"
            print(f"  实际意图：{actual_intent}  [{status}]")
            print(f"  地点    ：{[(loc.name, loc.role) for loc in intent.locations]}")
            if intent.time:
                print(f"  时间    ：date={intent.time.date}, "
                      f"start={intent.time.start_time}, end={intent.time.end_time}")
            print(f"  关注要素：{intent.variables}")
            print(f"  建议工具：{intent.needed_tools}")
            if intent.reasoning:
                print(f"  推理理由：{intent.reasoning}")
        except Exception as e:
            print(f"  错误    ：{e}")

    print("\n" + "=" * 80)
    print(f"测试结果：{pass_count} / {len(TEST_CASES)} 通过")
    print("=" * 80)


if __name__ == "__main__":
    run_tests()
