"""气温分级（确定性规则）

依据：
- ``grading_temperature_high_warning``：中央气象台高温预警三级（黄色 ≥35 ℃ /
  橙色 ≥37 ℃ / 红色 ≥40 ℃）
- ``grading_temperature_*``（< 35 ℃ 各级）：综合 GB 50736-2012《民用建筑
  供暖通风与空气调节设计规范》室内热舒适推荐区间（18–24 ℃）与公众气象
  服务一般用语；寒潮门槛参考 GB/T 21987-2017

输入：摄氏温度（float / int / "17°C" / "17.5℃" / "17"）
输出：``SemanticLabel``，其中 ``grade_id`` 对接 KB 中
``grading_temperature_*`` 一系列条目，可由 ``rag_enricher`` 按 ID 精确查表。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from src.analysis.schema import SemanticLabel


# (lo_inclusive, hi_inclusive, grade_name, grade_id)
# 阈值统一以"含下界、含上界"半开半闭区间表达，相邻档位互不重叠（取整到一位小数）。
TEMPERATURE_GRADES: List[Tuple[float, float, str, str]] = [
    (-99.9,    -0.1,   "寒冷",  "grading_temperature_cold"),
    (0.0,       9.9,   "偏冷",  "grading_temperature_chilly"),
    (10.0,     17.9,   "凉爽",  "grading_temperature_cool"),
    (18.0,     23.9,   "舒适",  "grading_temperature_comfortable"),
    (24.0,     29.9,   "温暖",  "grading_temperature_warm"),
    (30.0,     34.9,   "炎热",  "grading_temperature_hot"),
    (35.0,    999.0,   "高温",  "grading_temperature_high_warning"),
]


def classify_temperature(value_celsius: Optional[float]) -> SemanticLabel:
    """对气温（摄氏）做分级。

    Args:
        value_celsius: 摄氏温度（None 视为缺失）

    Returns:
        SemanticLabel，source 默认 ``rule_only``，可由 enricher 升级为
        ``rule_plus_rag``
    """
    if value_celsius is None:
        return SemanticLabel(
            variable="temp",
            raw_value="未知",
            grade=None,
            source="fallback",
            note="气温数据缺失",
        )

    raw = f"{value_celsius:.1f}°C"
    for lo, hi, grade, grade_id in TEMPERATURE_GRADES:
        if lo <= value_celsius <= hi:
            return SemanticLabel(
                variable="temp",
                raw_value=raw,
                grade=grade,
                grade_id=grade_id,
                source="rule_only",
            )

    last = TEMPERATURE_GRADES[-1]
    return SemanticLabel(
        variable="temp",
        raw_value=raw,
        grade=last[2],
        grade_id=last[3],
        source="rule_only",
        note="超出表内最高档位，按最高级处理",
    )


_TEMP_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_temperature(value) -> Optional[float]:
    """把 weather_api 工具返回的温度字段解析为 float（℃）。

    兼容格式：
        - int / float：``17`` / ``17.5`` → 17.0 / 17.5
        - 含单位文本：``"17°C"`` / ``"17.5℃"`` / ``"17 度"`` / ``"17C"`` → 17.0 / 17.5
        - 纯数字字符串：``"17"`` → 17.0
    解析失败返回 None。
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    m = _TEMP_NUMBER_RE.search(value)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


if __name__ == "__main__":
    samples = [None, -15, -5, 0, 5, 12, 18, 22, 28, 33, 36, 40, "17°C", "17.5℃", "abc"]
    for v in samples:
        parsed = parse_temperature(v) if not isinstance(v, (int, float)) else float(v) if v is not None else None
        label = classify_temperature(parsed)
        print(f"input={v!r:>10}  parsed={parsed!s:>6}  → grade={label.grade}  id={label.grade_id}  note={label.note}")
