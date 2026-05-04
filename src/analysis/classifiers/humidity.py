"""相对湿度分级（确定性规则）

依据：
- GB 50736-2012《民用建筑供暖通风与空气调节设计规范》：冬季室内相对
  湿度推荐 ≥ 30%、夏季舒适区 40%–60%
- ``grading_humidity_comfort``（已有）：综合舒适带 40%–60%

输入：相对湿度百分比（``50`` / ``"50%"``）
输出：``SemanticLabel``，``grade_id`` 对接 KB 中 ``grading_humidity_*``。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from src.analysis.schema import SemanticLabel


# (lo_inclusive_percent, hi_inclusive_percent, grade_name, grade_id)
HUMIDITY_GRADES: List[Tuple[float, float, str, str]] = [
    (0.0,    29.9,   "极干燥", "grading_humidity_very_dry"),
    (30.0,   39.9,   "干燥",   "grading_humidity_dry"),
    (40.0,   60.0,   "适宜",   "grading_humidity_comfort"),
    (60.1,   75.0,   "偏湿",   "grading_humidity_humid"),
    (75.1,   89.9,   "潮湿",   "grading_humidity_very_humid"),
    (90.0,  100.0,   "极潮湿", "grading_humidity_extreme"),
]


def classify_humidity(value_percent: Optional[float]) -> SemanticLabel:
    """对相对湿度做分级。

    Args:
        value_percent: 相对湿度百分比，0–100。负值或 None 视为缺失。

    Returns:
        SemanticLabel，source 默认 ``rule_only``
    """
    if value_percent is None:
        return SemanticLabel(
            variable="humidity",
            raw_value="未知",
            grade=None,
            source="fallback",
            note="相对湿度数据缺失",
        )

    if value_percent < 0 or value_percent > 100:
        return SemanticLabel(
            variable="humidity",
            raw_value=f"{value_percent:.1f}%",
            grade=None,
            source="fallback",
            note="相对湿度数据非法（应在 0–100 之间）",
        )

    raw = f"{value_percent:.1f}%"
    for lo, hi, grade, grade_id in HUMIDITY_GRADES:
        if lo <= value_percent <= hi:
            return SemanticLabel(
                variable="humidity",
                raw_value=raw,
                grade=grade,
                grade_id=grade_id,
                source="rule_only",
            )

    last = HUMIDITY_GRADES[-1]
    return SemanticLabel(
        variable="humidity",
        raw_value=raw,
        grade=last[2],
        grade_id=last[3],
        source="rule_only",
        note="超出表内最高档位，按最高级处理",
    )


_HUM_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_humidity(value) -> Optional[float]:
    """把工具返回的相对湿度字段解析为百分比 float。

    兼容格式：
        - int / float：``50`` / ``50.5`` → 50.0 / 50.5
        - 含 % 文本：``"50%"`` / ``"50.5 %"`` → 50.0 / 50.5
        - 纯数字字符串：``"50"`` → 50.0
    解析失败返回 None。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    m = _HUM_NUMBER_RE.search(value)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


if __name__ == "__main__":
    samples = [None, 20, 35, 50, 65, 80, 95, "50%", "65 %", "abc"]
    for v in samples:
        parsed = parse_humidity(v) if not isinstance(v, (int, float)) else float(v) if v is not None else None
        label = classify_humidity(parsed)
        print(f"input={v!r:>10}  parsed={parsed!s:>6}  → grade={label.grade}  id={label.grade_id}  note={label.note}")
