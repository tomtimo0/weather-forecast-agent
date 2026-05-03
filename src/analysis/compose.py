"""把多个 SemanticLabel 合成为 LLM 友好的语义文本块

设计目标：
- LLM 看到的是「数值 + 等级 + 影响 + 建议 + 出处」结构化文本，而非裸数字
- 出处显式列出，便于 LLM 在最终回答中引用，提升可追溯性
- 不输出 source / grade_id 等内部字段，减少噪声
"""

from typing import List

from src.analysis.schema import SemanticLabel


_VAR_DISPLAY_NAME = {
    "precip_24h": "24小时降水量",
    "precip_12h": "12小时降水量",
    "wind_scale": "风力",
    "temp": "气温",
    "humidity": "相对湿度",
    "visibility": "能见度",
}


def compose_labels_for_llm(labels: List[SemanticLabel]) -> str:
    """生成 LLM 可读的多行语义文本。

    示例输出：
    ```
    [24小时降水量] 35mm/24h → 大雨
      影响：雨势猛烈，能见度明显下降，地面易积水。
      依据：降水量等级（GB/T 28592-2012） §4.1（中国气象局）
    ```
    """
    if not labels:
        return "（无可桥接的气象要素）"

    blocks: List[str] = []
    for lbl in labels:
        display = _VAR_DISPLAY_NAME.get(lbl.variable, lbl.variable)
        head = f"[{display}] {lbl.raw_value}"
        if lbl.grade:
            head += f" → {lbl.grade}"

        lines = [head]
        if lbl.impact:
            lines.append(f"  影响：{lbl.impact}")
        if lbl.actions:
            lines.append(f"  建议：" + "；".join(lbl.actions))
        if lbl.citation:
            lines.append(f"  依据：{lbl.citation}")
        if lbl.note:
            lines.append(f"  备注：{lbl.note}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)
