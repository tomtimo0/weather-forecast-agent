"""能见度分级（确定性规则）

依据：
- GB/T 27964-2011《雾的预报等级》：雾 500–1000 m / 浓雾 50–500 m /
  强浓雾 < 50 m
- 中央气象台《大雾预警信号》：黄色 < 500 m / 橙色 < 200 m / 红色 < 50 m
- QX/T 113-2010《霾的观测和预报等级》：相对湿度 < 80% 时按能见度
  细分为轻微（5–10 km）/ 轻度（3–5 km）/ 中度（2–3 km）/ 重度（< 2 km）

输入：能见度数值（米；和风天气 ``vis`` 字段单位为 km，需要归一化）
输出：``SemanticLabel``，``grade_id`` 对接 KB 中 ``grading_visibility_*``。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from src.analysis.schema import SemanticLabel


# (lo_inclusive_meter, hi_inclusive_meter, grade_name, grade_id)
# 由低到高排序，便于"超出最大值则按最高级"的兜底语义保持一致。
# 含下界、含上界。
VISIBILITY_GRADES: List[Tuple[float, float, str, str]] = [
    (0.0,        49.9,    "极端低能见度",       "grading_visibility_extreme"),
    (50.0,      199.9,    "强浓雾",             "grading_visibility_heavy_dense_fog"),
    (200.0,     499.9,    "浓雾",               "grading_visibility_dense_fog"),
    (500.0,     999.9,    "雾",                 "grading_visibility_fog"),
    (1000.0,   4999.9,    "轻雾/轻霾",          "grading_visibility_mist"),
    (5000.0,   9999.9,    "良好",               "grading_visibility_good"),
    (10000.0,  9.9e9,     "极佳",               "grading_visibility_excellent"),
]


def classify_visibility(value_meter: Optional[float]) -> SemanticLabel:
    """对水平能见度做分级。

    Args:
        value_meter: 水平能见度（米；None / 负数视为缺失）

    Returns:
        SemanticLabel，source 默认 ``rule_only``
    """
    if value_meter is None:
        return SemanticLabel(
            variable="visibility",
            raw_value="未知",
            grade=None,
            source="fallback",
            note="能见度数据缺失",
        )

    if value_meter < 0:
        return SemanticLabel(
            variable="visibility",
            raw_value=f"{value_meter:.0f} m",
            grade=None,
            source="fallback",
            note="能见度数据非法（负数）",
        )

    raw = _format_visibility(value_meter)
    for lo, hi, grade, grade_id in VISIBILITY_GRADES:
        if lo <= value_meter <= hi:
            return SemanticLabel(
                variable="visibility",
                raw_value=raw,
                grade=grade,
                grade_id=grade_id,
                source="rule_only",
            )

    last = VISIBILITY_GRADES[-1]
    return SemanticLabel(
        variable="visibility",
        raw_value=raw,
        grade=last[2],
        grade_id=last[3],
        source="rule_only",
        note="超出表内最大档位，按最高级处理",
    )


def _format_visibility(value_meter: float) -> str:
    if value_meter >= 1000:
        return f"{value_meter / 1000:.1f} km"
    return f"{value_meter:.0f} m"


_VIS_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_visibility(value, unit: str = "m") -> Optional[float]:
    """把工具返回的能见度字段解析为米数。

    Args:
        value: 原始字段值，支持 int / float / 字符串（"800m" / "5 km" / "5"）
        unit: 当 value 是无单位数字（如 5）时的默认单位，``m`` 或 ``km``。
            和风天气 ``vis`` 字段返回的字符串以 km 为单位（如 "25"），
            实战中 dispatcher 会按字段名约定指定 unit。

    Returns:
        以米为单位的 float，解析失败返回 None。
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        v = float(value)
        return v * 1000.0 if unit == "km" else v

    if not isinstance(value, str):
        return None

    s = value.strip().lower()
    has_km = "km" in s
    has_m = "m" in s and not has_km
    m = _VIS_NUMBER_RE.search(s)
    if not m:
        return None
    try:
        v = float(m.group(0))
    except ValueError:
        return None

    if has_km:
        return v * 1000.0
    if has_m:
        return v
    return v * 1000.0 if unit == "km" else v


if __name__ == "__main__":
    samples = [None, 30, 100, 300, 800, 3000, 7000, 15000, "800m", "5 km", "25"]
    for v in samples:
        if isinstance(v, (int, float)):
            parsed = float(v) if v is not None else None
        else:
            parsed = parse_visibility(v, unit="m")
        label = classify_visibility(parsed)
        print(f"input={v!r:>10}  parsed={parsed!s:>10}m  → grade={label.grade}  id={label.grade_id}")
