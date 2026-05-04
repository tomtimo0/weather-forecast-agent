"""气象数据分析与语义桥接模块

把工具返回的原始气象数值转化为「分级 + 影响 + 建议 + 权威出处」的语义文本，
作为 LLM 之前的确定性预处理，降低数值幻觉。
"""

from src.analysis.schema import LabelSource, SemanticLabel
from src.analysis.semantic_bridge import BridgeMode, bridge_weather_dict

__all__ = [
    "LabelSource",
    "SemanticLabel",
    "BridgeMode",
    "bridge_weather_dict",
]
