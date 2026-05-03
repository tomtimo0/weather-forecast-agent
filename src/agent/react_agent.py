"""ReAct Agent 主控逻辑"""

from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from src.config.settings import LLM_MODEL, LLM_API_KEY, LLM_BASE_URL, SYSTEM_PROMPT
from src.intent.completer import complete_intent, format_completion_notes
from src.intent.recognizer import recognize_intent
from src.intent.schema import CompletionResult, WeatherIntent
from src.tools.knowledge_tool import search_knowledge
from src.tools.weather_api import (
    get_current_time,
    search_city,
    get_current_weather,
    get_forcast_weather,
    get_daily_forecast,
    get_weather_warning,
    get_weather_indices,
    get_historical_hourly,
    get_historical_daily,
)


@dataclass
class Context:
    """自定义运行时上下文模式。"""
    user_id: str


_agent_instance = None


def create_weather_agent():
    """创建天气查询 Agent 实例（全局单例，确保多轮对话共享同一份记忆）。"""
    global _agent_instance
    if _agent_instance is not None:
        return _agent_instance

    model = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )

    checkpointer = InMemorySaver()

    _agent_instance = create_agent(
        model=model,
        tools=[
            get_current_time,
            search_city,
            get_current_weather,
            get_forcast_weather,
            get_daily_forecast,
            get_weather_warning,
            get_weather_indices,
            get_historical_hourly,
            get_historical_daily,
            search_knowledge,
        ],
        context_schema=Context,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    return _agent_instance


def build_enhanced_query(query: str, completion: CompletionResult) -> str:
    """将意图识别 + 参数补全结果作为额外上下文与原始问题拼接。

    Args:
        query: 用户原始查询
        completion: 参数补全后的结果

    Returns:
        拼接后的增强查询，注入 Agent 的首条用户消息
    """
    intent = completion.completed_intent
    notes_text = format_completion_notes(completion.notes)
    notes_section = f"\n\n{notes_text}\n\n请在最终回答末尾用一两句话告知用户上述补全信息（仅在有补全时），便于用户确认。" if notes_text else ""

    return f"""用户原始问题：{query}

【意图识别 + 参数补全结果】
- 意图类型: {intent.intent}
- 涉及地点: {[(loc.name, loc.role) for loc in intent.locations]}
- 时间范围: {intent.time.model_dump() if intent.time else "未指定"}
- 关注要素: {intent.variables}
- 建议工具: {intent.needed_tools}
- 推理理由: {intent.reasoning}{notes_section}

请基于上述结构化意图调用合适的工具，回答用户的原始问题。"""


_conversation_history: list[str] = []


def run_agent(query: str, thread_id: str = "1"):
    """运行 Agent 并流式输出中间过程。

    流程：意图识别 → 参数补全 → 关键缺失则追问 → 注入 Agent 上下文 → 工具调用。

    Args:
        query: 用户输入的自然语言查询
        thread_id: 对话线程 ID，用于多轮对话
    """
    print("=== 意图识别 ===")
    intent = recognize_intent(query)
    print(intent.model_dump_json(indent=2))
    print()

    print("=== 参数补全 ===")
    history_context = "\n".join(_conversation_history[-6:]) if _conversation_history else None
    completion = complete_intent(intent, conversation_context=history_context)
    print(completion.model_dump_json(indent=2))
    print()

    if not completion.is_complete:
        question = completion.follow_up_question or "请补充更多信息以便我查询天气。"
        print(f"=== 追问用户 ===\n{question}\n")
        _conversation_history.append(f"用户: {query}")
        _conversation_history.append(f"助手追问: {question}")
        return

    enhanced_query = build_enhanced_query(query, completion)
    _conversation_history.append(f"用户: {query}")

    agent = create_weather_agent()
    config = {"configurable": {"thread_id": thread_id}}

    final_answer = ""
    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": enhanced_query}]},
        config=config,
        stream_mode="updates",
    ):
        for step, data in chunk.items():
            msg = data["messages"][-1]
            print(f"=== 步骤: {step} ===")

            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"  调用工具: {tc['name']}, 参数: {tc['args']}")
            elif step == "tools":
                print(f"  工具返回: {msg.content[:200]}...")
            else:
                print(msg.content)
                if step == "model" and msg.content:
                    final_answer = msg.content

            print()

    if final_answer:
        _conversation_history.append(f"助手: {final_answer[:200]}")


def chat_loop(thread_id: str = "1"):
    """启动多轮对话循环，输入 'exit' 或 'quit' 退出。"""
    print("天气助手已启动，输入问题开始对话（输入 exit 退出）\n")
    while True:
        query = input("你: ").strip()
        if query.lower() in ("exit", "quit", "q"):
            print("再见！")
            break
        if not query:
            continue
        run_agent(query, thread_id=thread_id)
        print()


if __name__ == "__main__":
    chat_loop()
