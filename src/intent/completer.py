"""缺失参数补全模块

接收意图识别模块输出的 WeatherIntent，判定关键参数是否齐全：
- 可推断的参数（默认值/上下文/常识）由 LLM 自动补全，并记录补全来源
- 关键参数缺失时返回追问问题，让 Agent 反问用户
"""

from datetime import datetime
from typing import List, Optional

from langchain_openai import ChatOpenAI

from src.config.settings import LLM_MODEL, LLM_API_KEY, LLM_BASE_URL
from src.intent.schema import WeatherIntent, CompletionResult


COMPLETER_PROMPT = """你是一个气象查询参数补全助手。
你的任务是检查 WeatherIntent 中的关键参数是否齐全：可补的自动补、补不了的追问用户。

## 各意图类型的关键参数清单
- current_weather: 必须有 locations
- hourly_forecast / daily_forecast: 必须有 locations 和 time.date
- weather_warning: 必须有 locations
- life_index: 必须有 locations 和 time.date
- historical_hourly / historical_daily: 必须有 locations、time.date（起止日期）
- travel_advice: 必须有至少 2 个 locations（出发地+目的地）和 time

## 自动补全规则（按优先级）
1. **default 默认值**：当用户未指明时间但意图允许时，默认补 time.date='今天'
2. **context_inference 上下文推断**：根据历史对话，例如用户上轮问过北京，本轮"那明天呢"则补 location='北京'
3. **common_sense 常识推断**：例如"早上"通常指 06:00-09:00，"晚上"指 18:00-21:00

## 关键参数判定与追问
- 若 locations 为空且无法从历史推断 → 关键缺失，is_complete=False，问"您想查询哪个城市？"
- 若历史查询要求精确日期但 time 完全为空 → 关键缺失，问"您想查询哪一天/哪段时间？"
- 若 travel_advice 只有一个地点 → 问"出发地是哪里？"或"目的地是哪里？"

## 输出要求
- 每条补全都要在 notes 中记录：field（字段路径）、value（补全值）、source（来源）、reason（解释）
- reason 用简洁的中文，会直接展示给用户，例如"未指定日期，默认查询今天"
- 关键参数齐全时 is_complete=True，follow_up_question=null
- 关键参数缺失时 is_complete=False，给出 1 句具体的追问

## 当前时间参考
当前日期：{current_date}
当前时间：{current_time}

## 历史对话上下文
{conversation_context}

## 已识别的原始意图
{original_intent}

请检查并输出 CompletionResult。"""


def create_completer():
    """创建参数补全 LLM。"""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=0,
    )
    return llm.with_structured_output(CompletionResult, method="function_calling")


def complete_intent(
    intent: WeatherIntent,
    conversation_context: Optional[str] = None,
) -> CompletionResult:
    """补全意图中的缺失参数。

    Args:
        intent: 意图识别模块输出的原始意图
        conversation_context: 历史对话摘要（可选），用于上下文推断

    Returns:
        CompletionResult: 补全结果，包含补全后意图、补全日志、追问问题
    """
    completer = create_completer()
    now = datetime.now()
    prompt = COMPLETER_PROMPT.format(
        current_date=now.strftime("%Y-%m-%d (%A)"),
        current_time=now.strftime("%H:%M"),
        conversation_context=conversation_context or "（无）",
        original_intent=intent.model_dump_json(indent=2),
    )

    return completer.invoke([
        {"role": "system", "content": prompt},
        {"role": "user", "content": "请补全或追问。"},
    ])


def format_completion_notes(notes: List) -> str:
    """把补全记录格式化为人类可读的简短文本，供 Agent 在最终回答时引用。"""
    if not notes:
        return ""
    lines = ["【参数补全说明】"]
    source_label = {
        "user_input": "用户提供",
        "context_inference": "上下文推断",
        "default": "默认值",
        "common_sense": "常识推断",
    }
    for note in notes:
        label = source_label.get(note.source, note.source)
        lines.append(f"- {note.field} = {note.value}（来源：{label}，{note.reason}）")
    return "\n".join(lines)


if __name__ == "__main__":
    from src.intent.recognizer import recognize_intent
    test_query = "明天天气怎么样？"
    intent = recognize_intent(test_query)
    print("原始意图：")
    print(intent.model_dump_json(indent=2))
    print("\n补全结果：")
    result = complete_intent(intent)
    print(result.model_dump_json(indent=2))
