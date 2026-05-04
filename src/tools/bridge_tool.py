"""语义桥接工具

把 `src.analysis.semantic_bridge.bridge_weather_dict` 包装为 LangChain Tool，
让 Agent 在需要对原始气象数值做"等级判定 + 影响 + 建议 + 权威依据"的语义解读时主动调用。

设计要点：
- 工具入参为 JSON 字符串，对应 weather_api 工具返回 dict 中的关键字段
  （例如 ``{"precip": "35mm"}``、``{"windScale": "7"}``）
- 桥接走"分类器 → grade_id → KB 精确查表"路径，零向量检索、零幻觉
- 当某要素无法分级或 KB 中未命中时，返回 fallback 标签并标注原因
- 默认 mode=rule_plus_rag；论文消融实验时可显式传 ``mode="rule_only"`` 跳过 RAG 富化
"""

import json
from typing import Optional

from langchain.tools import tool

from src.analysis.semantic_bridge import BridgeMode, bridge_weather_dict


@tool
def bridge_weather_data(
    data_json: str,
    scene: Optional[str] = None,
    mode: str = "rule_plus_rag",
) -> str:
    """对天气工具返回的原始数值做"等级判定 + 影响描述 + 出处引用"的语义桥接。

    应当在以下情形主动调用本工具（先调天气工具拿数据，再调本工具做解读）：
    - 用户询问"X mm 雨 / X 级风 / X 度气温"等数值的**等级判定**
    - 用户需要**作业建议**（高空作业 / 户外运动 / 出行 / 驾驶等）且涉及阈值判断
    - 需要在最终回答中**引用国标 / 行业规范条款**作为依据

    本工具对每个要素返回：原始值 → 分级名 → 影响描述 → 出处引用，全部基于
    确定性规则与权威知识库（GB/T 28592-2012 等），不依赖 LLM 自行推理。

    Args:
        data_json: 天气数据的 JSON 字符串，键为气象要素名，值为带单位的字符串或数值。
                   支持的键（缺失字段会被自动跳过，无需补全）：
                   - "precip" 或 "precip_24h"：24h 降水量，如 "35mm"
                   - "precip_12h"：12h 降水量
                   建议用法：把 get_current_weather / get_daily_forecast 等工具返回结果
                   中相关字段挑出来组成一个小 JSON 再传入。
        scene: 可选场景标签，用于裁剪不相关建议。常用：
               "出行" / "驾驶" / "高空作业" / "户外作业" / "农业" / "运动" / "生活"。
               传 None 时不做场景过滤。
        mode: 桥接模式，可选：
              - "rule_plus_rag"（默认）：本地分级 + RAG 权威条款富化，输出最完整
              - "rule_only"：仅本地分级，不查 RAG（消融对照）
              - "off"：不桥接（baseline，用于论文消融实验）

    Returns:
        多行文本块，每个要素一段，结构为：
        ```
        [24小时降水量] 35.0mm/24h → 大雨
          影响：雨势猛烈，能见度明显下降，地面易积水。
          依据：降水量等级（GB/T 28592-2012） §4.1（中国气象局）
        ```
        Agent 应在最终回答中保留分级名与依据出处。
    """
    try:
        data = json.loads(data_json) if isinstance(data_json, str) else dict(data_json)
    except Exception as exc:
        return f"（输入解析失败：data_json 必须是合法 JSON 字符串，错误：{exc}）"

    if not isinstance(data, dict):
        return "（输入解析失败：data_json 必须是 JSON 对象，例如 {\"precip\": \"35mm\"}）"

    bridge_mode: BridgeMode = mode if mode in ("off", "rule_only", "rule_plus_rag") else "rule_plus_rag"
    result = bridge_weather_dict(data, scene=scene, mode=bridge_mode)
    text = result.get("semantic_text") or "（无可桥接的气象要素；请确认 data_json 中包含 precip / precip_12h 等支持字段）"
    return text


if __name__ == "__main__":
    sample = json.dumps({"precip": "35mm", "precip_12h": "20mm"})
    print("=== rule_plus_rag（默认） ===")
    print(bridge_weather_data.invoke({"data_json": sample, "scene": "出行"}))
    print()
    print("=== rule_only（消融对照） ===")
    print(bridge_weather_data.invoke({"data_json": sample, "scene": "出行", "mode": "rule_only"}))
