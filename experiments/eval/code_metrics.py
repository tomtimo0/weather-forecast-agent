"""代码生成 / LLM 直算 评测指标

针对 ``data/test_cases/code_exec_bench.jsonl`` 中的统计分析任务，
对比"LLM 自由发挥直算"与"LLM 生成代码并执行"两种范式在数值准确率
上的差异，作为论文 Q3 章节"为什么必须做代码执行"的核心实证。

评测三档
--------
- ``llm_direct``：LLM 看 query + data，**禁止生成代码**，直接给数值
- ``llm_with_code``：LLM 生成 ``compute(data)`` 代码 → 受限沙箱执行
- ``oracle``：直接读 ``expected.value``（作为天花板，验证评测器自身正确性）

期望类型
--------
- ``scalar``：单个数值（含 tolerance）
- ``date`` / ``time``：日期或时间字符串
- ``date_with_value`` / ``time_with_value``：``{"date"/"time": ..., "<metric>": value}``
- ``ordered_list``：有序字符串列表（顺序敏感）

宽容比较（仅对 ``llm_direct``）
-------------------------------
LLM 直算输出的 value 可能是 ``"20.4°C"`` / ``"约 20 度"`` / ``20.4``——
用 ``_extract_number`` 先剥单位，再做 tolerance 比较。
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional


def load_bench(path: str) -> List[Dict[str, Any]]:
    """加载评测集 JSONL。"""
    cases: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except Exception as exc:
                raise ValueError(
                    f"评测集解析失败：{path}:{lineno} - {exc}"
                ) from exc
    return cases


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_number(raw: Any) -> Optional[float]:
    """尽力把任意输入转成 float：

    - ``20.4`` → 20.4
    - ``"20.4"`` → 20.4
    - ``"20.4°C"`` / ``"约 20.4 摄氏度"`` → 20.4
    - ``"无法计算"`` → None
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, str):
        m = _NUMBER_RE.search(raw)
        if m:
            try:
                return float(m.group())
            except ValueError:
                return None
    return None


def _normalize_date_str(raw: Any) -> Optional[str]:
    """把日期字符串归一化为 ``YYYY-MM-DD`` 形式，匹配失败返回 None。"""
    if raw is None:
        return None
    s = str(raw)
    m = re.search(r"(\d{4})[-/年.](\d{1,2})[-/月.](\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    return None


def _normalize_time_str(raw: Any) -> Optional[str]:
    """把时间字符串归一化为 ``HH:MM`` 形式。"""
    if raw is None:
        return None
    s = str(raw)
    m = re.search(r"(\d{1,2})[:：](\d{2})", s)
    if m:
        h, mi = m.groups()
        return f"{int(h):02d}:{int(mi):02d}"
    return None


def _scalar_match(pred: Any, expected: Any, tol: float) -> bool:
    p = _extract_number(pred)
    e = _extract_number(expected)
    if p is None or e is None:
        return False
    return abs(p - e) <= max(tol, 1e-9)


def _date_match(pred: Any, expected: Any) -> bool:
    return _normalize_date_str(pred) == _normalize_date_str(expected)


def _time_match(pred: Any, expected: Any) -> bool:
    return _normalize_time_str(pred) == _normalize_time_str(expected)


def _flatten_dict_for_value(pred: Any) -> Dict[str, Any]:
    """LLM 直算 value 可能是 dict / list / 字符串：尽力 flatten 成
    ``{<numeric_key>: float, <date_key>: "YYYY-MM-DD", "raw": orig}``，
    便于 date_with_value 比较。"""
    out: Dict[str, Any] = {"raw": pred}
    if isinstance(pred, dict):
        for k, v in pred.items():
            out[k] = v
    elif isinstance(pred, str):
        d = _normalize_date_str(pred)
        if d:
            out["date"] = d
        t = _normalize_time_str(pred)
        if t:
            out["time"] = t
        n = _extract_number(pred)
        if n is not None:
            out["_num"] = n
    return out


def _compare_value(
    pred: Any,
    expected_value: Any,
    expected_type: str,
    tolerance: float,
    numeric_extra: Optional[float] = None,
) -> bool:
    """统一比较函数：根据 expected_type 派遣到不同的子比较器。"""
    if expected_type == "scalar":
        return _scalar_match(pred, expected_value, tolerance)

    if expected_type == "date":
        return _date_match(pred, expected_value)

    if expected_type == "time":
        return _time_match(pred, expected_value)

    if expected_type in ("date_with_value", "time_with_value"):
        if not isinstance(expected_value, dict):
            return False
        flat = _flatten_dict_for_value(pred)
        # 比较日期/时间字段
        date_or_time_key = "date" if expected_type == "date_with_value" else "time"
        date_or_time_match = (
            _date_match if expected_type == "date_with_value" else _time_match
        )
        if not date_or_time_match(
            flat.get(date_or_time_key), expected_value.get(date_or_time_key)
        ):
            return False
        # 比较数值字段（允许从 numeric_extra 兜底）
        for k, v in expected_value.items():
            if k in (date_or_time_key,):
                continue
            pred_num = flat.get(k)
            if pred_num is None:
                pred_num = flat.get("_num")
            if pred_num is None:
                pred_num = numeric_extra
            if not _scalar_match(pred_num, v, tolerance):
                return False
        return True

    if expected_type == "ordered_list":
        if not isinstance(expected_value, list):
            return False
        if not isinstance(pred, list):
            return False
        if len(pred) != len(expected_value):
            return False
        for p, e in zip(pred, expected_value):
            if isinstance(e, str) and re.search(r"\d{4}", e):
                if not _date_match(p, e):
                    return False
            else:
                if str(p).strip() != str(e).strip():
                    return False
        return True

    return False


# ---------------------------------------------------------------------------
# 单条评测
# ---------------------------------------------------------------------------

def evaluate_case(
    case: Dict[str, Any],
    mode: str,
    pred_value: Any,
    pred_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """对单条用例计算指标。

    Args:
        case: 评测用例（含 ``expected``）
        mode: ``llm_direct`` / ``llm_with_code`` / ``oracle``
        pred_value: 预测的值（数值/字典/列表/字符串/None）
        pred_meta: mode-specific 元信息（例如 llm_with_code 的 ``code_generated`` /
            ``code_executable`` / ``error``；llm_direct 的 ``numeric_extra`` / ``error``）
    """
    expected = case["expected"]
    e_type = expected["type"]
    tol = float(expected.get("tolerance", 0))
    numeric_extra = (pred_meta or {}).get("numeric_extra")

    correct = _compare_value(pred_value, expected["value"], e_type, tol, numeric_extra)

    metrics: Dict[str, Any] = {
        "id": case["id"],
        "category": case["category"],
        "mode": mode,
        "expected_type": e_type,
        "expected_value": expected["value"],
        "pred_value": pred_value,
        "numeric_correct": correct,
    }
    if pred_meta:
        for k in ("code_generated", "code_executable", "error", "code", "reasoning"):
            if k in pred_meta:
                metrics[k] = pred_meta[k]
    return metrics


# ---------------------------------------------------------------------------
# 聚合
# ---------------------------------------------------------------------------

def _avg_bool(values: Iterable[bool]) -> Optional[float]:
    vals = [bool(v) for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def aggregate(case_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(case_metrics)
    if n == 0:
        return {"n_cases": 0}
    summary: Dict[str, Any] = {
        "n_cases": n,
        "numeric_accuracy": _avg_bool(m.get("numeric_correct") for m in case_metrics),
    }
    if any("code_generated" in m for m in case_metrics):
        summary["code_generated_rate"] = _avg_bool(
            m.get("code_generated") for m in case_metrics if "code_generated" in m
        )
    if any("code_executable" in m for m in case_metrics):
        summary["code_executable_rate"] = _avg_bool(
            m.get("code_executable") for m in case_metrics if "code_executable" in m
        )
    return summary


def aggregate_by_category(
    case_metrics: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in case_metrics:
        bucket[m.get("category") or "uncategorized"].append(m)
    return {cat: aggregate(items) for cat, items in bucket.items()}


__all__ = [
    "load_bench",
    "evaluate_case",
    "aggregate",
    "aggregate_by_category",
]
