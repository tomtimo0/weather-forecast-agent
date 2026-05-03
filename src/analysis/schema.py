"""语义桥接核心数据模型

`SemanticLabel` 描述"一个原始气象数值经过分级 + 影响 + 建议加工后的完整语义视图"，
是分类器（classifiers）→ 富化器（enrichers）→ 合成器（compose）三层之间的统一载体。
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# 桥接来源标注：用于消融实验对比"纯规则"vs"规则+RAG"
LabelSource = Literal[
    "rule_only",       # 等级名取自本地规则，无权威依据
    "rule_plus_rag",   # 等级名来自规则，影响/建议来自 RAG 权威条款
    "fallback",        # 数据缺失或无法分级
]


class SemanticLabel(BaseModel):
    """单个气象变量的语义标签。"""

    variable: str = Field(description="气象变量名，如 'precip_24h'、'wind_scale'、'temp'")
    raw_value: str = Field(description="原始值（含单位），如 '35mm'、'7级'、'17°C'")

    grade: Optional[str] = Field(
        default=None,
        description="分级名称，如 '大雨'、'疾风'、'凉爽'。无法分级时为 None",
    )
    grade_id: Optional[str] = Field(
        default=None,
        description="分级在 RAG 知识库中的唯一 ID，便于按 ID 精确查表",
    )

    impact: Optional[str] = Field(
        default=None,
        description="该等级对应的影响描述，优先来自 RAG 权威条款，次选 fallback 规则",
    )
    actions: List[str] = Field(
        default_factory=list,
        description="基于该等级的建议动作（按场景过滤后），如 ['注意防滑', '高空作业建议暂停']",
    )

    source: LabelSource = Field(
        default="rule_only", description="本条标签的加工来源，便于做消融对比"
    )
    citation: Optional[str] = Field(
        default=None,
        description="引用出处文本，如 'GB/T 28592-2012 §4.1'，写入最终回答以保可追溯",
    )
    note: Optional[str] = Field(
        default=None,
        description="附加说明，如 fallback 原因、数据缺失提示等",
    )
