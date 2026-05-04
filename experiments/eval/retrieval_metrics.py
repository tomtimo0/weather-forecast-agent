"""通路 A（search_knowledge）检索质量指标

针对 RAG 检索任务的标准评测指标：
- Recall@K：top-K 命中相关条目数 / 标注的相关条目总数
- Precision@K：top-K 命中相关条目数 / K
- MRR：第一个相关条目排名的倒数（top-K 内无命中则计 0）
- Category@K：top-K 中类别属于期望类别的条目占比
- top1_hit：top-1 是否命中相关条目（0/1）

评测数据格式约定（``data/test_cases/rag_retrieval_bench.jsonl``）：

```json
{
  "id": "term_001_drizzle",
  "category": "term",
  "description": "概念性问题：毛毛雨",
  "query": "什么是毛毛雨？",
  "relevant_ids": ["term_drizzle"],
  "expected_categories": ["term_definition"]
}
```
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence


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
                raise ValueError(f"评测集解析失败：{path}:{lineno} - {exc}") from exc
    return cases


def _topk(predicted_ids: Sequence[str], k: int) -> List[str]:
    return list(predicted_ids[:k])


def _topk_categories(
    predicted_ids: Sequence[str],
    id_to_category: Dict[str, str],
    k: int,
) -> List[str]:
    return [id_to_category.get(pid, "") for pid in predicted_ids[:k]]


def evaluate_case(
    case: Dict[str, Any],
    predicted_ids: Sequence[str],
    id_to_category: Dict[str, str],
    ks: Sequence[int] = (1, 3, 5),
) -> Dict[str, Any]:
    """对单条评测用例计算指标。

    Args:
        case: 评测用例（含 ``relevant_ids`` / ``expected_categories``）
        predicted_ids: 检索器返回的条目 ID 列表（按相关度降序）
        id_to_category: 全 KB 的 id → category 映射，用于 Category@K
        ks: 要计算的 K 值（默认 1/3/5）

    Returns:
        含以下字段的 dict：
        - id, category, query
        - top1_hit: bool
        - mrr: float
        - recall@K, precision@K, category@K（按 ks 展开）
        - n_relevant, predicted_top1
    """
    relevant_ids = set(case.get("relevant_ids", []))
    expected_categories = set(case.get("expected_categories", []))
    metrics: Dict[str, Any] = {
        "id": case.get("id"),
        "category": case.get("category"),
        "query": case.get("query"),
        "n_relevant": len(relevant_ids),
        "predicted_top1": predicted_ids[0] if predicted_ids else None,
    }

    metrics["top1_hit"] = bool(predicted_ids) and predicted_ids[0] in relevant_ids

    mrr = 0.0
    for rank, pid in enumerate(predicted_ids, 1):
        if pid in relevant_ids:
            mrr = 1.0 / rank
            break
    metrics["mrr"] = mrr

    for k in ks:
        topk_ids = _topk(predicted_ids, k)
        hit = len(set(topk_ids) & relevant_ids)
        metrics[f"recall@{k}"] = hit / len(relevant_ids) if relevant_ids else None
        metrics[f"precision@{k}"] = hit / k if k > 0 else None

        if expected_categories:
            cats = _topk_categories(predicted_ids, id_to_category, k)
            cat_hits = sum(1 for c in cats if c in expected_categories)
            metrics[f"category@{k}"] = cat_hits / k if k > 0 else None
        else:
            metrics[f"category@{k}"] = None

    return metrics


def _avg(values: Iterable[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None


def aggregate(
    case_metrics: List[Dict[str, Any]],
    ks: Sequence[int] = (1, 3, 5),
) -> Dict[str, Any]:
    """全量平均：每个指标做 macro-average。"""
    n = len(case_metrics)
    if n == 0:
        return {"n_cases": 0}
    summary: Dict[str, Any] = {
        "n_cases": n,
        "top1_hit_rate": sum(1 for m in case_metrics if m["top1_hit"]) / n,
        "mrr": _avg(m["mrr"] for m in case_metrics),
    }
    for k in ks:
        summary[f"recall@{k}"] = _avg(m[f"recall@{k}"] for m in case_metrics)
        summary[f"precision@{k}"] = _avg(m[f"precision@{k}"] for m in case_metrics)
        summary[f"category@{k}"] = _avg(m[f"category@{k}"] for m in case_metrics)
    return summary


def aggregate_by_category(
    case_metrics: List[Dict[str, Any]],
    ks: Sequence[int] = (1, 3, 5),
) -> Dict[str, Dict[str, Any]]:
    """按用例 category 字段分组聚合。"""
    bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in case_metrics:
        bucket[m.get("category") or "uncategorized"].append(m)
    return {cat: aggregate(items, ks=ks) for cat, items in bucket.items()}


__all__ = [
    "load_bench",
    "evaluate_case",
    "aggregate",
    "aggregate_by_category",
]
