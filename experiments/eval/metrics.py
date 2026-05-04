"""语义桥接评测指标定义

每条用例的「期望（expected）」与一次桥接调用的「实际输出（result）」做机器
比对，得到一组布尔/数值指标。再在数据集级别上做聚合（求平均、求子类目分布）。

指标分两层：
1. ``case_metrics``：单条用例级别（每条用例独立评判，得到布尔字段）
2. ``aggregate``：数据集级别（对若干条 case_metrics 做平均、按 category 拆分）

设计原则：
- **被测对象解耦**：metrics 不直接调用桥接，而是接收已计算好的 ``result`` 字典，
  方便将来同一套指标复用到其他被测对象（如纯 LLM baseline）
- **三档可比**：所有指标的 expected 来自数据集本身，对 mode=off / rule_only /
  rule_plus_rag 三档都用同一组期望去比对，分母一致

关键术语：
- ``coverage``：是否成功生成 SemanticLabel（≥1 条）
- ``n_labels_match``：标签条数与期望一致
- ``grade_accuracy``：所有期望 variable 的 grade 字段都正确
- ``grade_id_accuracy``：所有期望 variable 的 grade_id 都正确（更严格，区分 24h/12h）
- ``citation_rate``：所有 ``must_cite_rag`` 关键字都出现在 semantic_text 中
- ``citation_negative_pass``：所有 ``must_not_cite_rag`` 关键字都不在 semantic_text 中
  （用于场景过滤负例：当 scene 不匹配时，不应吐出 citation）
- ``source_match``：标签的 source 字段与 ``expected_source_rag`` 一致
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def evaluate_case(expected: Dict[str, Any], result: Dict[str, Any], mode: str) -> Dict[str, Any]:
    """对单条用例的桥接结果做指标计算。

    Args:
        expected: 用例的 expected 字典（来自评测集 JSONL）
        result: ``bridge_weather_dict`` 的返回值
        mode: 当前桥接模式（off / rule_only / rule_plus_rag）

    Returns:
        指标字典；布尔指标用 0/1 表示便于后续求平均
    """
    labels = result.get("labels", []) or []
    text = result.get("semantic_text", "") or ""

    expected_n = expected.get("n_labels", 0)
    expected_labels: Dict[str, Dict[str, Any]] = expected.get("labels", {}) or {}
    must_cite: List[str] = expected.get("must_cite_rag", []) or []
    must_not_cite: List[str] = expected.get("must_not_cite_rag", []) or []
    expected_source_rag: Optional[str] = expected.get("expected_source_rag")

    by_var = {lbl.variable: lbl for lbl in labels}

    if expected_n > 0:
        coverage = 1 if labels else 0
    else:
        coverage = None
    n_labels_match = 1 if len(labels) == expected_n else 0

    grade_correct = _all_match(expected_labels, by_var, "grade")
    grade_id_correct = _all_match(expected_labels, by_var, "grade_id")

    if mode == "rule_plus_rag":
        citation_rate = 1 if all(kw in text for kw in must_cite) else 0
        citation_negative_pass = 1 if all(kw not in text for kw in must_not_cite) else 0
        source_match = _check_source(by_var, expected_labels, expected_source_rag)
    else:
        citation_rate = None
        citation_negative_pass = None
        source_match = None

    if mode == "off":
        text_empty = 1 if text == "" else 0
    else:
        text_empty = None

    return {
        "mode": mode,
        "coverage": coverage,
        "n_labels_match": n_labels_match,
        "grade_accuracy": grade_correct,
        "grade_id_accuracy": grade_id_correct,
        "citation_rate": citation_rate,
        "citation_negative_pass": citation_negative_pass,
        "source_match": source_match,
        "text_empty": text_empty,
        "actual_n_labels": len(labels),
        "actual_text_len": len(text),
    }


def _all_match(expected_labels: Dict[str, Dict[str, Any]], by_var: Dict, key: str) -> int:
    """所有期望 variable 的 ``key`` 字段在实际输出中均一致 → 1，否则 0。

    若期望 labels 为空（fallback 用例），且实际也为空，记 1（一致）。
    """
    if not expected_labels:
        return 1 if not by_var else 0
    for var, exp in expected_labels.items():
        actual_lbl = by_var.get(var)
        if actual_lbl is None:
            return 0
        actual_value = getattr(actual_lbl, key, None)
        if actual_value != exp.get(key):
            return 0
    return 1


def _check_source(
    by_var: Dict,
    expected_labels: Dict[str, Dict[str, Any]],
    expected_source: Optional[str],
) -> Optional[int]:
    """对每个期望 variable 的 label.source 与 ``expected_source`` 比对。"""
    if not expected_source or not expected_labels:
        return None
    for var in expected_labels:
        lbl = by_var.get(var)
        if lbl is None:
            return 0
        if lbl.source != expected_source:
            return 0
    return 1


def aggregate(case_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """对若干条 case_metrics 做数据集级别聚合。

    返回字段：
        - 各指标的均值（百分比，保留 1 位小数）
        - 总用例数 / 通过率
    None 值不参与平均（仅在适用 mode 下有定义的指标）。
    """
    if not case_results:
        return {}

    keys = [
        "coverage", "n_labels_match", "grade_accuracy", "grade_id_accuracy",
        "citation_rate", "citation_negative_pass", "source_match", "text_empty",
    ]
    out: Dict[str, Any] = {"n_cases": len(case_results)}
    for k in keys:
        vals = [c[k] for c in case_results if c.get(k) is not None]
        if vals:
            out[k] = round(sum(vals) / len(vals) * 100, 1)
            out[f"{k}_n"] = len(vals)
        else:
            out[k] = None
            out[f"{k}_n"] = 0
    return out


def aggregate_by_category(
    case_results: List[Dict[str, Any]],
    cases: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """按用例 category 拆分聚合。

    Args:
        case_results: 与 cases 等长，第 i 项是 cases[i] 的 case_metrics
        cases: 原始用例 dict 列表（用于读取 category）
    """
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for case, res in zip(cases, case_results):
        by_cat.setdefault(case.get("category", "unknown"), []).append(res)
    return {cat: aggregate(items) for cat, items in by_cat.items()}
