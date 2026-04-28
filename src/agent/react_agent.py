"""ReAct Agent 主控逻辑"""

from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from src.config.settings import LLM_MODEL, LLM_API_KEY, LLM_BASE_URL, SYSTEM_PROMPT
from src.intent.recognizer import recognize_intent
from src.intent.schema import WeatherIntent
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
        ],
        context_schema=Context,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    return _agent_instance


def build_enhanced_query(query: str, intent: WeatherIntent) -> str:
    """将意图识别结果作为额外上下文与原始问题拼接。

    Args:
        query: 用户原始查询
        intent: 已识别的结构化意图

    Returns:
        拼接后的增强查询，注入 Agent 的首条用户消息
    """
    return f"""用户原始问题：{query}

【意图识别模块预解析结果】
- 意图类型: {intent.intent}
- 涉及地点: {[(loc.name, loc.role) for loc in intent.locations]}
- 时间范围: {intent.time.model_dump() if intent.time else "未指定"}
- 关注要素: {intent.variables}
- 建议工具: {intent.needed_tools}
- 推理理由: {intent.reasoning}

请基于上述结构化意图调用合适的工具，回答用户的原始问题。"""


def run_agent(query: str, thread_id: str = "1"):
    """运行 Agent 并流式输出中间过程。

    流程：先用意图识别模块解析用户问题，再把结构化意图注入 Agent 上下文。

    Args:
        query: 用户输入的自然语言查询
        thread_id: 对话线程 ID，用于多轮对话
    """
    print("=== 意图识别 ===")
    intent = recognize_intent(query)
    print(intent.model_dump_json(indent=2))
    print()

    enhanced_query = build_enhanced_query(query, intent)

    agent = create_weather_agent()
    config = {"configurable": {"thread_id": thread_id}}

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

            print()


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
