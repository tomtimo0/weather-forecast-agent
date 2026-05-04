"""语义桥接入口

把任意工具返回的气象数据 dict（如 weather_api 工具的输出）
经过「分类 → 富化 → 合成」三步，加工为 LLM 友好的语义文本。

当前覆盖要素：
    - 24h / 12h 降水量
    - 蒲福风级（windScale / windScaleDay / windScaleNight）

后续按 temp / humidity / visibility 等扩展 classifiers + 注册到 dispatcher 即可。
"""

from typing import Dict, List, Literal, Optional

from src.analysis.classifiers.precipitation import (
    classify_precipitation,
    parse_precip_value,
)
from src.analysis.classifiers.wind_scale import (
    classify_wind_scale,
    parse_wind_scale,
)
from src.analysis.compose import compose_labels_for_llm
from src.analysis.enrichers.rag_enricher import enrich_with_rag
from src.analysis.schema import SemanticLabel


# 桥接模式：用于消融实验对比
BridgeMode = Literal[
    "off",             # 不桥接，原样返回（baseline，幻觉对照组）
    "rule_only",       # 仅本地规则分级，不查 RAG
    "rule_plus_rag",   # 规则分级 + RAG 富化（推荐）
]


def bridge_weather_dict(
    data: Dict,
    scene: Optional[str] = None,
    mode: BridgeMode = "rule_plus_rag",
) -> Dict:
    """对工具返回的气象数据做语义桥接。

    Args:
        data: weather_api 工具的返回 dict，例如 {"precip_24h": "35mm", ...}
        scene: 场景标签（如 '出行'、'高空作业'），用于裁剪不相关建议
        mode: 桥接模式（off/rule_only/rule_plus_rag）

    Returns:
        {
            "raw": data,                # 原始数据，便于 Agent 在需要时查阅
            "semantic_text": "...",     # 给 LLM 的语义文本块
            "labels": [SemanticLabel],  # 结构化标签，便于下游程序使用
            "mode": mode,
        }
    """
    if mode == "off":
        return {"raw": data, "semantic_text": "", "labels": [], "mode": mode}

    labels: List[SemanticLabel] = []
    for label in _classify_all(data):
        if label is None:
            continue
        if mode == "rule_plus_rag":
            label = enrich_with_rag(label, scene=scene)
        labels.append(label)

    return {
        "raw": data,
        "semantic_text": compose_labels_for_llm(labels),
        "labels": labels,
        "mode": mode,
    }


def _classify_all(data: Dict) -> List[Optional[SemanticLabel]]:
    """根据 data 中存在的字段调用对应分类器，缺失的字段跳过。

    每加一个 classifier，在此处加一段字段名调度即可。
    """
    out: List[Optional[SemanticLabel]] = []

    # 24h 降水量：兼容多种字段名（precip_24h / precip / 和风返回的 precip）
    for key in ("precip_24h", "precip"):
        if key in data:
            v = parse_precip_value(data[key])
            if v is not None:
                out.append(classify_precipitation(v, "24h"))
            break

    # 12h 降水量
    if "precip_12h" in data:
        v = parse_precip_value(data["precip_12h"])
        if v is not None:
            out.append(classify_precipitation(v, "12h"))

    # 风力等级：和风返回的字段名是 windScale / windScaleDay / windScaleNight
    # 同一调用通常只关注其中一项；按"显式 wind_scale > 通用 windScale > 白天 > 夜间"优先级取首个非空
    for key in ("wind_scale", "windScale", "windScaleDay", "windScaleNight"):
        if key in data:
            v = parse_wind_scale(data[key])
            if v is not None:
                out.append(classify_wind_scale(v))
            break

    return out


if __name__ == "__main__":
    # 模拟和风天气 get_current_weather 的部分返回
    sample = {"temp": "17°C", "precip": "35mm", "windScale": "7级"}

    print("=== mode=off（baseline）===")
    print(bridge_weather_dict(sample, mode="off")["semantic_text"] or "(空)")

    print("\n=== mode=rule_only ===")
    print(bridge_weather_dict(sample, mode="rule_only")["semantic_text"])

    print("\n=== mode=rule_plus_rag（推荐）===")
    print(bridge_weather_dict(sample, scene="出行", mode="rule_plus_rag")["semantic_text"])
