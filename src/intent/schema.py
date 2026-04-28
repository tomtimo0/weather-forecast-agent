"""气象查询意图的结构化数据模型"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# 支持的意图类型
IntentType = Literal[
    "current_weather",     # 实时天气
    "hourly_forecast",     # 逐小时预报
    "daily_forecast",      # 逐日预报
    "weather_warning",     # 天气预警
    "life_index",          # 生活指数
    "historical_hourly",   # 历史逐小时
    "historical_daily",    # 历史逐日
    "travel_advice",       # 出行/旅行建议（需多工具组合）
    "unknown",             # 无法识别
]


class LocationIntent(BaseModel):
    """地点意图：用户提到的某个地理位置及其在场景中的角色。"""

    name: str = Field(description="地点名称，如'北京'、'武汉'、'天府新区'")
    role: Optional[Literal["target", "departure", "arrival", "waypoint"]] = Field(
        default="target",
        description="地点角色：target 单一查询目标，departure 出发地，arrival 目的地，waypoint 途经点",
    )


class TimeIntent(BaseModel):
    """时间意图：用户描述的查询时间范围。"""

    raw_text: Optional[str] = Field(
        default=None, description="用户原始时间表达，如'明天早八到晚六'、'去年这个月'"
    )
    date: Optional[str] = Field(
        default=None,
        description="日期描述，可以是相对（'今天'、'明天'、'后天'）或绝对（'2025-01-01'）",
    )
    start_time: Optional[str] = Field(
        default=None, description="开始时间，HH:MM 格式，如'08:00'"
    )
    end_time: Optional[str] = Field(
        default=None, description="结束时间，HH:MM 格式，如'18:00'"
    )


class WeatherIntent(BaseModel):
    """完整的气象查询意图。"""

    intent: IntentType = Field(description="意图类型")
    locations: List[LocationIntent] = Field(
        default_factory=list, description="涉及的所有地点"
    )
    time: Optional[TimeIntent] = Field(default=None, description="查询时间范围")
    variables: List[str] = Field(
        default_factory=list,
        description="关注的天气要素，如 ['temperature', 'precipitation', 'wind']",
    )
    needed_tools: List[str] = Field(
        default_factory=list, description="建议调用的工具名列表"
    )
    reasoning: Optional[str] = Field(
        default=None, description="意图判定的简短理由，便于调试"
    )
