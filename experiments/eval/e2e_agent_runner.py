"""端到端评测专用 Agent runner：full vs ablated 双档对照

设计目标
--------
为 ``run_e2e_eval.py`` 提供两档可对比的 Agent 实例：

- ``full``：与 ``src/agent/react_agent.py`` 等价——挂载全部 11 个工具
  （9 个气象 API + ``search_knowledge`` + ``bridge_weather_data``），
  使用完整 ``SYSTEM_PROMPT``（含双通路 RAG 调用规则段）
- ``ablated``：去掉 ``search_knowledge`` + ``bridge_weather_data`` 两个 RAG 工具，
  并在 system prompt 中删除"知识检索规则"与"语义桥接调用约束"两段，
  模拟"普通工程师不做双通路 RAG 时直接用 LLM + 9 个 API"的常见做法

两档共享：
- 同一个 LLM（GLM-5.1）
- 同一份意图识别 + 参数补全前置（保证输入侧公平）
- 同一份气象 API 工具（保证数据获取能力一致）

关键差异：
- full 能调 RAG 获取权威条款 / 通过 bridge 获取标准化分级 + 出处
- ablated 拿到原始 API 数据后，**只能由 LLM 自由发挥解读**

调用入口
--------
``run_one_query(mode, query, completion)`` →
``{"answer": str, "tool_calls": [...], "elapsed_ms": float}``

每次调用都用独立 ``thread_id``，避免多轮上下文污染评测。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from src.agent.react_agent import build_enhanced_query
from src.config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, SYSTEM_PROMPT
from src.intent.schema import CompletionResult
from src.tools.bridge_tool import bridge_weather_data
from src.tools.knowledge_tool import search_knowledge
from src.tools.weather_api import (
    get_current_time,
    get_current_weather,
    get_daily_forecast,
    get_forcast_weather,
    get_historical_daily,
    get_historical_hourly,
    get_weather_indices,
    get_weather_warning,
    search_city,
)


@dataclass
class _Context:
    user_id: str = "e2e_eval"


# ---------------------------------------------------------------------------
# 两档 prompt
# ---------------------------------------------------------------------------

# full 档直接复用 src.config.settings.SYSTEM_PROMPT
FULL_SYSTEM_PROMPT = SYSTEM_PROMPT


# ablated 档：去掉双通路 RAG 强制规则，模拟"普通工程师"做法
ABLATED_SYSTEM_PROMPT = """你是一个天气查询助手。

## 可用工具
### 数据查询类（提供"事实数据"）
- get_current_time: 获取当前日期时间
- search_city: 根据城市名搜索 LocationID 和经纬度
- get_current_weather: 获取实时天气（参数：LocationID）
- get_forcast_weather: 获取逐小时预报（参数：LocationID + 24h/72h/168h）
- get_daily_forecast: 获取逐日预报（参数：LocationID + 3d/7d/10d/15d/30d）
- get_weather_warning: 获取天气预警（参数：纬度 + 经度，需从 search_city 结果中获取）
- get_weather_indices: 获取天气生活指数（参数：LocationID + 1d/3d + 类型ID，"0"表示全部）
- get_historical_hourly: 查询历史逐小时天气（参数：纬度 + 经度 + 起止日期）
- get_historical_daily: 查询历史逐日天气（参数：纬度 + 经度 + 起止日期）

## 工具使用规则
1. 用户提到地名时，先用 search_city 获取 LocationID 和经纬度
2. 根据用户需求选择合适的天气工具：
   - 问"现在天气" → get_current_weather
   - 问"几点的天气"或精确到小时 → get_forcast_weather
   - 问"这几天"或"这周" → get_daily_forecast
   - 问"有没有预警"或涉及极端天气 → get_weather_warning
   - 问"适不适合运动/洗车/出行"或穿衣建议 → get_weather_indices
   - 问"去年/上个月/历史上"某地天气 → get_historical_daily 或 get_historical_hourly
3. 用户提到相对时间（今天、明天等）时，先调用 get_current_time 确定当前日期
4. 查询预警时，使用 search_city 返回的 lat/lon 作为 get_weather_warning 的参数
5. 历史数据工具使用 search_city 返回的 lat/lon 作为参数

## 出行场景推理规则
当用户描述从A地到B地的出行计划时：
- 出发时间段：使用 **出发地（A地）** 对应时段的天气
- 到达时间段：使用 **目的地（B地）** 对应时段的天气

## 输出规则
- 精准定位用户需要的时间、地点、天气参数
- 不输出用户不在场的时间地点的天气
- 如有预警信息，优先在回答开头提醒用户
- 给出实用的穿衣/出行建议
- 涉及分级判断或作业适宜性结论时，结合气象数据自行解读"""


# ---------------------------------------------------------------------------
# 两档 agent 单例
# ---------------------------------------------------------------------------

_full_agent = None
_ablated_agent = None

_BASE_TOOLS = [
    get_current_time,
    search_city,
    get_current_weather,
    get_forcast_weather,
    get_daily_forecast,
    get_weather_warning,
    get_weather_indices,
    get_historical_hourly,
    get_historical_daily,
]

_RAG_TOOLS = [
    search_knowledge,
    bridge_weather_data,
]


def _create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=0,
        timeout=90,
        max_retries=2,
    )


def _get_full_agent():
    global _full_agent
    if _full_agent is None:
        from src.rag.knowledge_base import get_knowledge_base
        from src.rag.retriever import get_retriever
        # 提前热身 RAG 单例避免并发冷启动
        get_knowledge_base()
        get_retriever()
        _full_agent = create_agent(
            model=_create_llm(),
            tools=_BASE_TOOLS + _RAG_TOOLS,
            context_schema=_Context,
            system_prompt=FULL_SYSTEM_PROMPT,
            checkpointer=InMemorySaver(),
        )
    return _full_agent


def _get_ablated_agent():
    global _ablated_agent
    if _ablated_agent is None:
        _ablated_agent = create_agent(
            model=_create_llm(),
            tools=_BASE_TOOLS,
            context_schema=_Context,
            system_prompt=ABLATED_SYSTEM_PROMPT,
            checkpointer=InMemorySaver(),
        )
    return _ablated_agent


def get_agent(mode: str):
    """根据 mode 返回 Agent 实例。"""
    if mode == "full":
        return _get_full_agent()
    if mode == "ablated":
        return _get_ablated_agent()
    raise ValueError(f"未知 mode: {mode}（仅支持 full / ablated）")


# ---------------------------------------------------------------------------
# 单次调用
# ---------------------------------------------------------------------------

def run_one_query(
    mode: str,
    query: str,
    completion: CompletionResult,
    max_iters: int = 30,
) -> Dict[str, Any]:
    """对单条查询跑一遍 Agent，返回回答与工具调用 trace。

    Args:
        mode: ``full`` / ``ablated``
        query: 用户原始查询
        completion: 已完成的意图识别 + 补全结果
        max_iters: 防爆保险——计的是 ``stream_mode="updates"`` 下的 chunk 数，
            不是 react 循环数。full 档因为有 search_knowledge + bridge_weather_data
            额外两次 RAG 调用，单条用例可能产生 ~20 个 chunk，故默认放宽到 30。

    Returns:
        ``{"answer", "tool_calls", "elapsed_ms", "error", "iter_count"}``
    """
    agent = get_agent(mode)
    enhanced_query = build_enhanced_query(query, completion)
    config = {"configurable": {"thread_id": uuid.uuid4().hex}}

    started = time.perf_counter()
    final_answer = ""
    tool_calls: List[Dict[str, Any]] = []
    iter_count = 0
    error: Optional[str] = None

    try:
        for chunk in agent.stream(
            {"messages": [{"role": "user", "content": enhanced_query}]},
            config=config,
            stream_mode="updates",
        ):
            iter_count += 1
            if iter_count > max_iters:
                error = f"达到 max_iters={max_iters}，强制中止"
                break
            for step, data in chunk.items():
                msg = data["messages"][-1]
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "name": tc.get("name", ""),
                            "args": tc.get("args", {}),
                        })
                elif step == "model" and getattr(msg, "content", ""):
                    final_answer = msg.content
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "answer": final_answer,
        "tool_calls": tool_calls,
        "elapsed_ms": elapsed_ms,
        "error": error,
        "iter_count": iter_count,
    }


__all__ = ["run_one_query", "get_agent", "FULL_SYSTEM_PROMPT", "ABLATED_SYSTEM_PROMPT"]
