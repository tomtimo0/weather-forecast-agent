"""ReAct Agent 主控逻辑"""

from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

from src.config.settings import LLM_MODEL, LLM_API_KEY, LLM_BASE_URL, SYSTEM_PROMPT
from src.tools.weather_api import (
    get_current_time,
    search_city,
    get_current_weather,
    get_forcast_weather,
    get_daily_forecast,
    get_weather_warning,
    get_weather_indices,
)


@dataclass
class Context:
    """自定义运行时上下文模式。"""
    user_id: str


def create_weather_agent():
    """创建天气查询 Agent 实例。"""
    model = ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )

    checkpointer = InMemorySaver()

    agent = create_agent(
        model=model,
        tools=[
            get_current_time,
            search_city,
            get_current_weather,
            get_forcast_weather,
            get_daily_forecast,
            get_weather_warning,
            get_weather_indices,
        ],
        context_schema=Context,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )
    return agent


def run_agent(query: str, thread_id: str = "1"):
    """运行 Agent 并流式输出中间过程。

    Args:
        query: 用户输入的自然语言查询
        thread_id: 对话线程 ID，用于多轮对话
    """
    agent = create_weather_agent()
    config = {"configurable": {"thread_id": thread_id}}

    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": query}]},
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


if __name__ == "__main__":
    run_agent("武汉未来一周一周哪几天适合骑车？")
