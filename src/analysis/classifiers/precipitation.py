"""降水量分级（确定性规则，依据 GB/T 28592-2012）

输入：降水量数值（mm）+ 时间窗口
输出：SemanticLabel，其中 grade_id 与 RAG 知识库中的条目 ID 一一对应
"""

from typing import Literal, Optional

from src.analysis.schema import SemanticLabel


# 24 小时降水量分级阈值表（依据 GB/T 28592-2012 §4.1）
# 元组 (下界含, 上界含, grade_name, grade_id)
PRECIP_24H_GRADES = [
    (0.0,    0.099,  "无降水或微量",     None),  # < 0.1mm
    (0.1,    9.9,    "小雨",            "grading_precip_24h_light"),
    (10.0,   24.9,   "中雨",            "grading_precip_24h_moderate"),
    (25.0,   49.9,   "大雨",            "grading_precip_24h_heavy"),
    (50.0,   99.9,   "暴雨",            "grading_precip_24h_rainstorm"),
    (100.0,  249.9,  "大暴雨",          "grading_precip_24h_heavy_rainstorm"),
    (250.0,  9999.0, "特大暴雨",        "grading_precip_24h_extreme_rainstorm"),
]

# 12 小时降水量分级阈值表
PRECIP_12H_GRADES = [
    (0.0,   0.099,  "无降水或微量", None),
    (0.1,   4.9,    "小雨",        "grading_precip_12h_light"),
    (5.0,   14.9,   "中雨",        "grading_precip_12h_moderate"),
    (15.0,  29.9,   "大雨",        "grading_precip_12h_heavy"),
    (30.0,  69.9,   "暴雨",        "grading_precip_12h_rainstorm"),
]


def classify_precipitation(
    value_mm: float,
    time_window: Literal["24h", "12h"] = "24h",
) -> SemanticLabel:
    """对降水量做分级。

    Args:
        value_mm: 降水量数值，单位毫米
        time_window: 时间窗口，目前支持 24h / 12h

    Returns:
        SemanticLabel，其中 grade_id 可被 enricher 用来查 RAG
    """
    table = PRECIP_24H_GRADES if time_window == "24h" else PRECIP_12H_GRADES
    variable = f"precip_{time_window}"
    raw = f"{value_mm}mm/{time_window}"

    if value_mm is None or value_mm < 0:
        return SemanticLabel(
            variable=variable,
            raw_value=raw,
            grade=None,
            source="fallback",
            note="降水量数据缺失或非法",
        )

    for lo, hi, grade, grade_id in table:
        if lo <= value_mm <= hi:
            return SemanticLabel(
                variable=variable,
                raw_value=raw,
                grade=grade,
                grade_id=grade_id,
                source="rule_only",
            )

    return SemanticLabel(
        variable=variable,
        raw_value=raw,
        grade=table[-1][2],
        grade_id=table[-1][3],
        source="rule_only",
        note="超出表内最大档位，按最高级处理",
    )


def parse_precip_value(value) -> Optional[float]:
    """把 weather_api 工具返回的"35.0mm"或"35.0"或数字解析为 float。

    工具层为了 LLM 可读做了 f"{x}mm" 的拼接，桥接层需要剥离单位。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().lower().rstrip("mm").strip()
        try:
            return float(s)
        except ValueError:
            return None
    return None


if __name__ == "__main__":
    samples = [0, 0.05, 5.0, 15.0, 35.0, 80.0, 150.0, 300.0]
    for v in samples:
        label = classify_precipitation(v, "24h")
        print(f"{v}mm/24h → grade={label.grade}, id={label.grade_id}")
