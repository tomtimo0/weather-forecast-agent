"""气象要素确定性分类器集合

每个分类器独立成模块，对外暴露：
    - ``classify_xxx(value)``：核心分级函数，返回 ``SemanticLabel``
    - ``parse_xxx(value)``：解析工具层字段（含单位、范围）为标准数值
    - 分级阈值常量，便于评测脚本与文档引用

新增要素时仅需在 ``semantic_bridge._classify_all`` 加一段调度。
"""

from src.analysis.classifiers.humidity import (
    HUMIDITY_GRADES,
    classify_humidity,
    parse_humidity,
)
from src.analysis.classifiers.precipitation import (
    PRECIP_12H_GRADES,
    PRECIP_24H_GRADES,
    classify_precipitation,
    parse_precip_value,
)
from src.analysis.classifiers.temperature import (
    TEMPERATURE_GRADES,
    classify_temperature,
    parse_temperature,
)
from src.analysis.classifiers.visibility import (
    VISIBILITY_GRADES,
    classify_visibility,
    parse_visibility,
)
from src.analysis.classifiers.wind_scale import (
    WIND_BEAUFORT_GRADES,
    classify_wind_scale,
    classify_wind_speed,
    parse_wind_scale,
)

__all__ = [
    "PRECIP_24H_GRADES",
    "PRECIP_12H_GRADES",
    "classify_precipitation",
    "parse_precip_value",
    "WIND_BEAUFORT_GRADES",
    "classify_wind_scale",
    "classify_wind_speed",
    "parse_wind_scale",
    "TEMPERATURE_GRADES",
    "classify_temperature",
    "parse_temperature",
    "VISIBILITY_GRADES",
    "classify_visibility",
    "parse_visibility",
    "HUMIDITY_GRADES",
    "classify_humidity",
    "parse_humidity",
]
