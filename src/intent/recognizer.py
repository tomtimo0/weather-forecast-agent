"""气象查询意图识别器"""

from langchain_openai import ChatOpenAI

from src.config.settings import LLM_MODEL, LLM_API_KEY, LLM_BASE_URL
from src.intent.schema import WeatherIntent


INTENT_RECOGNIZER_PROMPT = """你是一个气象查询意图识别器。
你的任务是将用户的自然语言气象查询，解析为结构化的查询意图。

## 意图类型说明
- current_weather: 用户问"现在/此刻"的天气
- hourly_forecast: 用户问未来某几个小时或精确到小时的天气
- daily_forecast: 用户问未来几天/这周/这个月的整体天气
- weather_warning: 用户问"有没有预警"或涉及暴雨、台风、高温等极端天气
- life_index: 用户问"适不适合"做某事（运动、洗车、出行、晾衣等）或穿衣建议
- historical_hourly: 用户问过去某天/某段时间逐小时的天气
- historical_daily: 用户问过去某段时间逐日或长期天气
- travel_advice: 用户描述从A地到B地的出行计划，需要综合多个时间和地点的天气
- unknown: 无法识别为以上任一类型

## 地点角色
- target: 单一查询目标（默认）
- departure: 出发地
- arrival: 目的地
- waypoint: 途经点

## 工具映射参考
- current_weather → search_city + get_current_weather
- hourly_forecast → search_city + get_forcast_weather
- daily_forecast → search_city + get_daily_forecast
- weather_warning → search_city + get_weather_warning
- life_index → search_city + get_weather_indices
- historical_hourly → search_city + get_historical_hourly
- historical_daily → search_city + get_historical_daily
- travel_advice → search_city + get_forcast_weather + get_weather_indices

涉及相对时间（今天、明天等）时，需额外加 get_current_time。

## 注意
- 仔细识别用户提到的所有地点，并标注角色
- 准确提取时间范围，包括日期、起止时间
- 在 reasoning 字段简短说明你为何这样判定，方便调试

请根据以上规则解析用户问题。"""


def create_recognizer():
    """创建意图识别 LLM（绑定 WeatherIntent 结构化输出）。"""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=0,
    )
    # DeepSeek/SiliconFlow 等第三方平台不支持 response_format json_schema，
    # 改用 function_calling 方式实现结构化输出
    return llm.with_structured_output(WeatherIntent, method="function_calling")


def recognize_intent(query: str) -> WeatherIntent:
    """识别用户查询的气象意图。

    Args:
        query: 用户的自然语言查询

    Returns:
        WeatherIntent: 结构化意图对象
    """
    recognizer = create_recognizer()
    return recognizer.invoke([
        {"role": "system", "content": INTENT_RECOGNIZER_PROMPT},
        {"role": "user", "content": query},
    ])


if __name__ == "__main__":
    test_query = "明天早八到晚六，从成都坐高铁到武汉，有什么穿衣建议？"
    intent = recognize_intent(test_query)
    print(intent.model_dump_json(indent=2))
