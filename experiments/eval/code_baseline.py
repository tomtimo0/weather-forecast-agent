"""LLM 直算 baseline：让 LLM 在不写代码的情况下直接根据数据给出数值答案

公平性原则
----------
- prompt 给 LLM 完整数据，但**禁止生成代码**，只能直接给数值答案
- prompt 不告诉 LLM 期望答案的精度
- 让 LLM **完全凭内置算术能力**作答，得到的 baseline 才能真实反映
  LLM 在不依赖代码执行时的「数值计算幻觉」风险

输出 schema 与 ``code_executor.ExecutionResult`` 兼容（仅取 value 字段），
便于评测脚本统一处理。

缓存机制
--------
- 默认缓存到 ``experiments/results/code_baseline_cache.json``
- 同一 (query, data, prompt_version, model) 组合命中缓存直接返回
- ``--force-llm`` 重新清空缓存调 LLM
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


BASELINE_PROMPT_VERSION = "v1"


BASELINE_SYSTEM_PROMPT = """你是一个气象数据分析助手。
用户会给你一段自然语言查询和一份完整的数据，请你**直接**给出最终数值答案。

## 重要约束
1. 不要写代码、不要展示计算过程的代码片段
2. 直接给出数值答案（数值/字符串/字典/列表中的一种）
3. 涉及四舍五入时一律保留 1 位小数
4. 当用户问的是"哪一天"或"哪个城市"时，``value`` 应是日期串或城市名（字符串），同时把对应数值放在 ``numeric_extra`` 字段
5. 当任务无法计算或数据不足时，把 ``error`` 字段设为简短理由，``value`` 留空

## 输出
请输出一个结构化对象，包含 ``value`` 与 ``reasoning`` 字段。"""


class LLMDirectAnswer(BaseModel):
    """LLM 不写代码直接给出的数值答案。"""

    value: Optional[Any] = Field(
        default=None,
        description="最终答案：数值/字符串/字典/列表（与 expected.value 同构）",
    )
    numeric_extra: Optional[float] = Field(
        default=None,
        description="当 value 是字符串（如日期/城市）时，可在此放对应的数值（如温差/降水量）",
    )
    reasoning: Optional[str] = Field(
        default=None, description="1-2 句简短解释，用于调试"
    )
    error: Optional[str] = Field(
        default=None, description="无法计算时的简短理由（成功时留空）"
    )


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------

DEFAULT_CACHE_PATH = os.path.join(
    "experiments", "results", "code_baseline_cache.json"
)


def _make_cache_key(query: str, data: Any, model: str) -> str:
    payload = json.dumps(
        {
            "q": query,
            "d": data,
            "v": BASELINE_PROMPT_VERSION,
            "m": model,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


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

_baseline_singleton = None


def _get_baseline_llm():
    """惰性创建 LLM 客户端单例（带 timeout / max_retries 加固）。"""
    global _baseline_singleton
    if _baseline_singleton is None:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=0,
            timeout=60,
            max_retries=2,
        )
        _baseline_singleton = llm.with_structured_output(
            LLMDirectAnswer, method="function_calling"
        )
    return _baseline_singleton


def _truncate_data_for_prompt(data: Any, max_chars: int = 1500) -> str:
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [已截断，原始 {len(text)} 字符]"


def run_llm_direct(
    query: str,
    data: Any,
    cache: Optional[Dict[str, Any]] = None,
    max_retries: int = 1,
) -> Dict[str, Any]:
    """让 LLM 不写代码直接给出数值答案。

    Returns:
        ``{"value", "numeric_extra", "reasoning", "error", "cache_hit", "raw"}``
    """
    cache_key = _make_cache_key(query, data, LLM_MODEL)
    if cache is not None and cache_key in cache:
        cached = cache[cache_key]
        return {**cached, "cache_hit": True}

    structured = _get_baseline_llm()
    user_msg = (
        f"## 查询\n{query}\n\n"
        f"## 完整数据\n```json\n{_truncate_data_for_prompt(data)}\n```"
    )
    last_error = ""
    answer: Optional[LLMDirectAnswer] = None
    for _attempt in range(max_retries + 1):
        try:
            raw = structured.invoke([
                {"role": "system", "content": BASELINE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ])
            if isinstance(raw, LLMDirectAnswer):
                answer = raw
                break
            last_error = "LLM 未触发结构化输出"
        except Exception as exc:  # noqa: BLE001
            last_error = f"调用异常：{exc}"

    if answer is None:
        answer = LLMDirectAnswer(value=None, error=last_error)

    out = {
        "value": answer.value,
        "numeric_extra": answer.numeric_extra,
        "reasoning": answer.reasoning,
        "error": answer.error,
        "cache_hit": False,
        "raw": answer.model_dump(),
    }
    if cache is not None:
        cache[cache_key] = {
            "value": answer.value,
            "numeric_extra": answer.numeric_extra,
            "reasoning": answer.reasoning,
            "error": answer.error,
            "raw": answer.model_dump(),
        }
    return out


if __name__ == "__main__":
    sample_data = {
        "daily": [
            {"date": "2025-04-01", "tempMax": 18.5},
            {"date": "2025-04-02", "tempMax": 20.3},
            {"date": "2025-04-03", "tempMax": 22.7},
        ],
    }
    cache = load_cache()
    res = run_llm_direct("这3天最高温的平均是多少？", sample_data, cache=cache)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    save_cache(cache)
