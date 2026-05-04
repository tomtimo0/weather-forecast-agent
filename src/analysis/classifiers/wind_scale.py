"""风力分级（蒲福风级，依据 GB/T 28591-2012 / WMO Beaufort scale）

输入：
    - 蒲福风级整数 0–12（来自和风天气 windScale 字段）
    - 或风速 m/s（备用入口）

输出：SemanticLabel，其中 grade_id 与 RAG 知识库中
``grading_wind_beaufort_<n>`` 一一对齐，便于 enricher 按 ID 精确查表。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.analysis.schema import SemanticLabel


# (grade_int, name_zh, ms_low, ms_high, grade_id)
# 数值范围依据 GB/T 28591-2012 / WMO Beaufort scale（米/秒，10 米标准高度处）。
WIND_BEAUFORT_GRADES: List[Tuple[int, str, float, float, str]] = [
    (0,  "无风",   0.0,    0.2,    "grading_wind_beaufort_0"),
    (1,  "软风",   0.3,    1.5,    "grading_wind_beaufort_1"),
    (2,  "轻风",   1.6,    3.3,    "grading_wind_beaufort_2"),
    (3,  "微风",   3.4,    5.4,    "grading_wind_beaufort_3"),
    (4,  "和风",   5.5,    7.9,    "grading_wind_beaufort_4"),
    (5,  "清劲风", 8.0,    10.7,   "grading_wind_beaufort_5"),
    (6,  "强风",   10.8,   13.8,   "grading_wind_beaufort_6"),
    (7,  "疾风",   13.9,   17.1,   "grading_wind_beaufort_7"),
    (8,  "大风",   17.2,   20.7,   "grading_wind_beaufort_8"),
    (9,  "烈风",   20.8,   24.4,   "grading_wind_beaufort_9"),
    (10, "狂风",   24.5,   28.4,   "grading_wind_beaufort_10"),
    (11, "暴风",   28.5,   32.6,   "grading_wind_beaufort_11"),
    (12, "飓风",   32.7,   9999.0, "grading_wind_beaufort_12"),
]


def classify_wind_scale(scale: Optional[int]) -> SemanticLabel:
    """对蒲福风级整数（0–12）做分级。

    Args:
        scale: 蒲福风级整数（None / 负数视为缺失；> 12 钳制为 12）

    Returns:
        SemanticLabel，source 默认为 ``rule_only``，可经 enricher 升级为
        ``rule_plus_rag``
    """
    if scale is None:
        return SemanticLabel(
            variable="wind_scale",
            raw_value="未知",
            grade=None,
            source="fallback",
            note="风力等级缺失",
        )

    s = int(scale)
    raw = f"{s}级"
    if s < 0:
        return SemanticLabel(
            variable="wind_scale",
            raw_value=raw,
            grade=None,
            source="fallback",
            note="风力等级非法（负数）",
        )

    note: Optional[str] = None
    if s > 12:
        note = "超出蒲福风级表上限，按 12 级飓风处理"
        s = 12

    grade_int, name, _lo, _hi, grade_id = WIND_BEAUFORT_GRADES[s]
    return SemanticLabel(
        variable="wind_scale",
        raw_value=raw,
        grade=name,
        grade_id=grade_id,
        source="rule_only",
        note=note,
    )


def classify_wind_speed(value_ms: Optional[float]) -> SemanticLabel:
    """按风速 m/s 分级（备用入口；主流程走 ``classify_wind_scale``）。"""
    if value_ms is None:
        return SemanticLabel(
            variable="wind_scale",
            raw_value="未知",
            grade=None,
            source="fallback",
            note="风速数据缺失",
        )

    raw = f"{value_ms:.1f} m/s"
    if value_ms < 0:
        return SemanticLabel(
            variable="wind_scale",
            raw_value=raw,
            grade=None,
            source="fallback",
            note="风速非法（负数）",
        )

    for _grade_int, name, lo, hi, grade_id in WIND_BEAUFORT_GRADES:
        if lo <= value_ms <= hi:
            return SemanticLabel(
                variable="wind_scale",
                raw_value=raw,
                grade=name,
                grade_id=grade_id,
                source="rule_only",
            )

    last = WIND_BEAUFORT_GRADES[-1]
    return SemanticLabel(
        variable="wind_scale",
        raw_value=raw,
        grade=last[1],
        grade_id=last[4],
        source="rule_only",
        note="超出蒲福风级表上限，按 12 级飓风处理",
    )


def parse_wind_scale(value) -> Optional[int]:
    """解析 weather_api 的 windScale 字段为整数蒲福风级。

    兼容格式：
        - int / float：``7`` → 7
        - 单值文本：``"7"``、``"7级"`` → 7
        - 范围文本：``"1-3级"``、``"1-3"`` → 取上界 3（保守原则：按可能
          出现的最大风力提示，避免低估风险）
    解析失败返回 None。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None

    s = value.strip().rstrip("级").strip()
    if not s:
        return None

    if "-" in s or "~" in s:
        sep = "-" if "-" in s else "~"
        parts = [p.strip() for p in s.split(sep) if p.strip()]
        if len(parts) >= 2:
            try:
                return int(float(parts[1]))
            except ValueError:
                return None
        return None

    try:
        return int(float(s))
    except ValueError:
        return None


if __name__ == "__main__":
    # 简单自检
    samples = [None, 0, 1, 3, 5, 7, 8, 12, 15, "7级", "1-3级", "1~3", "abc"]
    for v in samples:
        scale = parse_wind_scale(v) if not isinstance(v, int) else v
        if v is None:
            scale = None
        label = classify_wind_scale(scale)
        print(f"input={v!r:>10}  parsed={scale!s:>4}  → grade={label.grade}  id={label.grade_id}  note={label.note}")
