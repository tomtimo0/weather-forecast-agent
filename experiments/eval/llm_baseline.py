"""LLM baseline：让 LLM 在不依赖外部知识库与确定性桥接的情况下，
直接根据原始气象数值给出分级名 + 影响 + 引用条款。

公平性原则：
- prompt **不**告诉 LLM 具体分级阈值（如"≥50mm 是暴雨"）
- prompt **不**告诉 LLM 具体标准编号（如"GB/T 28592-2012"）
- 只告诉它"任务是分级 + 给出权威依据"，让它**完全凭内置知识自由发挥**
- 这样得到的 baseline 才能真实反映 LLM 在没有 RAG / 桥接时的「数值幻觉」风险

输出 schema 与 ``bridge_weather_dict`` 同构，可直接送 ``evaluate_case`` 评估。

缓存机制：
- 默认缓存到 ``experiments/results/llm_baseline_cache.json``
- 同一 (input, scene, prompt_version, model) 组合命中缓存直接返回
- ``--force`` 重新清空缓存调 LLM
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


# 修改 prompt 时升级版本号，可让缓存自动失效
BASELINE_PROMPT_VERSION = "v1"

BASELINE_SYSTEM_PROMPT = """你是一个气象数据分级专家。

## 任务
根据用户给定的气象数值（来自工具返回的原始 JSON），输出每个变量的：
1. 中文分级名（如"小雨/中雨/大雨/暴雨"、"无风/软风/.../飓风"）
2. 该等级的实际影响描述（1-2 句）
3. **权威标准编号 + 条款号**（例如"GB/T 28592-2012 §4.1（中国气象局）"）

## 输入字段映射规则
- precip / precip_24h → 24小时累积降水量 → 输出 variable="precip_24h"
- precip_12h → 12小时累积降水量 → 输出 variable="precip_12h"
- windScale / windScaleDay / windScaleNight → 蒲福风级 → 输出 variable="wind_scale"
- temp → 气温 → 输出 variable="temp"
- humidity → 相对湿度 → 输出 variable="humidity"
- 其他字段：忽略，不输出

## 范围字段处理
若原始值是范围（如"1-3级"），按上界处理（保守原则：按可能的最大风力提示）。

## 重要约束
1. **必须给出 citation**，不允许空着、不允许写"无"或"未知"，必须是真实存在的国标 / 行业标准 / 部门规章。
2. 凡 input 中存在的可分级字段都要输出对应 label；若数值无法解析（如 "abc"），不要输出该 label。
3. 不要编造 input 中不存在的字段，不要为非分级字段（如 temp、humidity）强行制造分级。
4. variable 字段必须严格使用上面列出的规范化名称。

## 场景适用性
若指定了 scene 参数，请评估该等级在该场景下是否相关：
- 相关：正常输出 grade / impact / citation
- 不相关：仍输出 label 但 impact / citation 可留空（让下游评测识别）
"""


class LLMBaselineLabel(BaseModel):
    """LLM baseline 输出的单个分级标签（与 SemanticLabel 同构）"""

    variable: str = Field(
        description="规范化的气象变量名：precip_24h/precip_12h/wind_scale/temp/humidity"
    )
    raw_value: str = Field(description="原始数值含单位，如 '35mm' / '7级'")
    grade: Optional[str] = Field(
        default=None, description="LLM 推断的分级中文名"
    )
    grade_id: Optional[str] = Field(
        default=None,
        description="LLM 凭印象给出的分级 ID（用于诊断；可留空）",
    )
    impact: Optional[str] = Field(default=None, description="该等级的实际影响描述")
    citation: Optional[str] = Field(
        default=None, description="LLM 给出的权威标准号 + 条款号"
    )


class LLMBaselineResult(BaseModel):
    """LLM baseline 对一条 case 的完整输出"""

    labels: List[LLMBaselineLabel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 适配器：让 LLMBaselineLabel 与 metrics.evaluate_case 期望的 SemanticLabel 同构
# ---------------------------------------------------------------------------

class _AdaptedLabel:
    """把 LLMBaselineLabel 包装成有 ``.source`` 属性的对象，便于评测脚本统一处理。"""

    __slots__ = ("variable", "raw_value", "grade", "grade_id", "impact", "citation", "source")

    def __init__(self, lbl: LLMBaselineLabel, source: str = "llm_baseline") -> None:
        self.variable = lbl.variable
        self.raw_value = lbl.raw_value
        self.grade = lbl.grade
        self.grade_id = lbl.grade_id
        self.impact = lbl.impact
        self.citation = lbl.citation
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variable": self.variable,
            "raw_value": self.raw_value,
            "grade": self.grade,
            "grade_id": self.grade_id,
            "impact": self.impact,
            "citation": self.citation,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "_AdaptedLabel":
        obj = cls.__new__(cls)
        for k in cls.__slots__:
            setattr(obj, k, d.get(k))
        return obj


def _compose_baseline_text(labels: List[_AdaptedLabel]) -> str:
    """把 labels 拼成 LLM 友好文本，便于 must_cite 关键字检查（与 compose 模块输出格式对齐）。"""
    if not labels:
        return ""
    blocks: List[str] = []
    for lbl in labels:
        head = f"[{lbl.variable}] {lbl.raw_value}"
        if lbl.grade:
            head += f" → {lbl.grade}"
        lines = [head]
        if lbl.impact:
            lines.append(f"  影响：{lbl.impact}")
        if lbl.citation:
            lines.append(f"  依据：{lbl.citation}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CACHE_PATH = os.path.join(
    _PROJECT_ROOT, "experiments", "results", "llm_baseline_cache.json"
)


def _make_cache_key(input_dict: Dict[str, Any], scene: Optional[str], model: str) -> str:
    """对 (input, scene, prompt_version, model) 做 sha256 摘要，作为缓存键。"""
    payload = {
        "input": input_dict,
        "scene": scene,
        "prompt_version": BASELINE_PROMPT_VERSION,
        "model": model,
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def load_cache(path: str = DEFAULT_CACHE_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache: Dict[str, Any], path: str = DEFAULT_CACHE_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 主接口
# ---------------------------------------------------------------------------

_llm_singleton = None


def _get_llm():
    """惰性创建 LLM 客户端单例。"""
    global _llm_singleton
    if _llm_singleton is None:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=0,
        )
        _llm_singleton = llm.with_structured_output(
            LLMBaselineResult, method="function_calling"
        )
    return _llm_singleton


def run_llm_baseline(
    input_dict: Dict[str, Any],
    scene: Optional[str] = None,
    cache: Optional[Dict[str, Any]] = None,
    max_retries: int = 1,
) -> Dict[str, Any]:
    """对一条 case 跑 LLM baseline，返回与 ``bridge_weather_dict`` 同构的 result dict。

    Args:
        input_dict: 原始气象数据 dict
        scene: 场景标签（可选）
        cache: 缓存字典（可被外部累积写入）；为 None 时不缓存
        max_retries: 结构化输出失败时的额外重试次数

    Returns:
        ``{"raw", "semantic_text", "labels", "mode": "llm_baseline"}``
    """
    cache_key = _make_cache_key(input_dict, scene, LLM_MODEL)
    if cache is not None and cache_key in cache:
        cached = cache[cache_key]
        labels = [_AdaptedLabel.from_dict(d) for d in cached.get("labels", [])]
        return {
            "raw": input_dict,
            "semantic_text": cached.get("semantic_text", ""),
            "labels": labels,
            "mode": "llm_baseline",
            "cache_hit": True,
        }

    structured = _get_llm()
    user_msg = (
        f"input: {json.dumps(input_dict, ensure_ascii=False)}\n"
        f"scene: {scene if scene else '（未指定）'}"
    )
    last_error = ""
    result: Optional[LLMBaselineResult] = None
    for _attempt in range(max_retries + 1):
        try:
            raw = structured.invoke([
                {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ])
            if isinstance(raw, LLMBaselineResult):
                result = raw
                break
            last_error = "LLM 未触发结构化输出（function_calling 偶发失败）"
        except Exception as exc:  # noqa: BLE001
            last_error = f"调用异常：{exc}"

    if result is None:
        result = LLMBaselineResult(labels=[])

    adapted = [_AdaptedLabel(lbl) for lbl in result.labels]
    text = _compose_baseline_text(adapted)
    out = {
        "raw": input_dict,
        "semantic_text": text,
        "labels": adapted,
        "mode": "llm_baseline",
        "cache_hit": False,
    }
    if last_error:
        out["llm_error"] = last_error

    if cache is not None:
        cache[cache_key] = {
            "labels": [a.to_dict() for a in adapted],
            "semantic_text": text,
            "llm_error": last_error,
        }
    return out


if __name__ == "__main__":
    sample_inputs = [
        ({"precip": "35mm"}, "出行"),
        ({"windScale": "7级"}, "高空作业"),
        ({"precip": "abc"}, None),
    ]
    cache = load_cache()
    print(f"加载缓存：{len(cache)} 条")
    for i, (inp, sc) in enumerate(sample_inputs, 1):
        print(f"\n--- 样例 {i}: input={inp}, scene={sc} ---")
        out = run_llm_baseline(inp, sc, cache=cache)
        print(f"cache_hit={out.get('cache_hit')}")
        print(f"semantic_text:\n{out['semantic_text']}")
    save_cache(cache)
    print(f"\n缓存已保存：{len(cache)} 条")
