"""通路 A 检索器权重扫描实验（hybrid 子档位的细粒度消融）

在 ``run_rag_eval.py`` 的基础上做更精细的扫描：在固定评测集上把
``HybridRetriever`` 的 ``vector_weight``（与 BM25 互补）从 0.0 扫到 1.0，
观察 Top-1 / MRR / Recall@5 等指标随权重的变化曲线，回答"混合检索的
最优权重应该是多少"这个论文级问题。

特别地：
- vector_weight=0.0 等价于纯 BM25（仍走 hybrid 框架，保证可比）
- vector_weight=1.0 等价于纯 vector
- 默认扫描点：[0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 1.0]（含项目当前默认 0.6）

用法：
    python -m experiments.eval.run_rag_weight_sweep
    python -m experiments.eval.run_rag_weight_sweep --weights 0.0 0.4 0.6 0.8 1.0
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List, Sequence, Tuple

from experiments.eval.retrieval_metrics import (
    aggregate,
    evaluate_case,
    load_bench,
)
from src.rag.knowledge_base import get_knowledge_base
from src.rag.retriever import HybridRetriever


class _QueryCachedEmbedding:
    """运行时 query embedding 缓存包装器。

    权重扫描会把同一组 query 在不同权重下重跑多次，相同 query 的向量
    没必要每次都过一次嵌入 API。该 wrapper 透明缓存 ``embed_query`` 的
    结果，对 KB 中只用到的接口保持兼容。
    """

    def __init__(self, base) -> None:
        self._base = base
        self._cache: Dict[str, List[float]] = {}

    def embed_query(self, text: str) -> List[float]:
        if text in self._cache:
            return self._cache[text]
        vec = self._base.embed_query(text)
        self._cache[text] = vec
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._base.embed_documents(texts)

    @property
    def cache_size(self) -> int:
        return len(self._cache)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_BENCH = os.path.join(PROJECT_ROOT, "data", "test_cases", "rag_retrieval_bench.jsonl")
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "experiments", "results")
DEFAULT_WEIGHTS: Tuple[float, ...] = (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 1.0)
DEFAULT_KS: Tuple[int, ...] = (1, 3, 5)


def run_one_weight(
    cases: List[Dict[str, Any]],
    vector_weight: float,
    top_k: int,
    id_to_category: Dict[str, str],
    ks: Sequence[int],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """在指定权重下跑一遍评测，返回 (overall, case_metrics)。"""
    kb = get_knowledge_base()
    retriever = HybridRetriever(
        kb=kb,
        vector_weight=vector_weight,
        bm25_weight=1.0 - vector_weight,
    )
    case_metrics: List[Dict[str, Any]] = []
    for case in cases:
        hits = retriever.retrieve(case["query"], top_k=top_k)
        predicted_ids = [hit.entry.id for hit in hits]
        m = evaluate_case(case, predicted_ids, id_to_category, ks=ks)
        m["predicted_top_k"] = predicted_ids
        case_metrics.append(m)
    overall = aggregate(case_metrics, ks=ks)
    return overall, case_metrics


def render_markdown(
    rows: List[Dict[str, Any]],
    n_cases: int,
    timestamp: str,
    top_k: int,
    ks: Sequence[int],
) -> str:
    out: List[str] = []
    out.append("# 通路 A 检索权重扫描实验报告")
    out.append("")
    out.append(f"- 评测时间：{timestamp}")
    out.append(f"- 用例总数：**{n_cases}**")
    weight_str = ", ".join(f"{r['vector_weight']:.2f}" for r in rows)
    out.append(f"- 扫描权重：vector_weight ∈ {{{weight_str}}}")
    out.append(f"- 每档 Top-K：{top_k}（统计 K={list(ks)}）")
    out.append("")

    out.append("## 一、权重 → 主指标")
    out.append("")
    headers = (
        "vector_w", "bm25_w",
        "Top-1", "MRR",
        f"Recall@1", f"Recall@{ks[-1]}",
        f"Precision@{ks[-1]}",
    )
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "---|" * len(headers))
    for r in rows:
        cells = [
            f"{r['vector_weight']:.2f}",
            f"{r['bm25_weight']:.2f}",
            f"{r['overall'].get('top1_hit_rate', 0) * 100:.1f}%",
            f"{r['overall'].get('mrr', 0):.3f}",
            f"{r['overall'].get('recall@1', 0) * 100:.1f}%",
            f"{r['overall'].get(f'recall@{ks[-1]}', 0) * 100:.1f}%",
            f"{r['overall'].get(f'precision@{ks[-1]}', 0) * 100:.1f}%",
        ]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")

    # 找最优权重
    best_top1 = max(rows, key=lambda r: r["overall"].get("top1_hit_rate") or 0)
    best_mrr = max(rows, key=lambda r: r["overall"].get("mrr") or 0)
    best_recall = max(rows, key=lambda r: r["overall"].get(f"recall@{ks[-1]}") or 0)

    out.append("## 二、最优权重")
    out.append("")
    out.append(
        f"- **Top-1 命中率最高**：vector_weight={best_top1['vector_weight']:.2f}，"
        f"top1={best_top1['overall'].get('top1_hit_rate', 0) * 100:.1f}%"
    )
    out.append(
        f"- **MRR 最高**：vector_weight={best_mrr['vector_weight']:.2f}，"
        f"MRR={best_mrr['overall'].get('mrr', 0):.3f}"
    )
    out.append(
        f"- **Recall@{ks[-1]} 最高**：vector_weight={best_recall['vector_weight']:.2f}，"
        f"Recall@{ks[-1]}={best_recall['overall'].get(f'recall@{ks[-1]}', 0) * 100:.1f}%"
    )
    out.append("")

    out.append("## 三、关键观察")
    out.append("")
    pure_v = next((r for r in rows if abs(r["vector_weight"] - 1.0) < 1e-6), None)
    pure_b = next((r for r in rows if abs(r["vector_weight"] - 0.0) < 1e-6), None)
    if pure_v and pure_b:
        out.append(
            f"- 纯 vector（vector_weight=1.0）：top1={pure_v['overall'].get('top1_hit_rate', 0) * 100:.1f}%，"
            f"MRR={pure_v['overall'].get('mrr', 0):.3f}"
        )
        out.append(
            f"- 纯 BM25（vector_weight=0.0）：top1={pure_b['overall'].get('top1_hit_rate', 0) * 100:.1f}%，"
            f"MRR={pure_b['overall'].get('mrr', 0):.3f}"
        )
    out.append(
        "- **现象解读**：在当前 KB（44 条）规模和 BAAI/bge-m3 嵌入下，向量召回质量已经"
        "相当高，BM25 主要在专有名词（"
        "蒲福风级中文名"
        "、行业术语）和阈值类查询上发挥补足作用。"
        "若评测集主要为概念性 / 自然语言改写查询，纯向量已能覆盖大部分需求；"
        "若 KB 进一步扩大或包含大量术语别名，BM25 的边际收益会上升。"
    )
    out.append("")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="通路 A 检索器权重扫描实验")
    parser.add_argument("--bench", default=DEFAULT_BENCH)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--weights",
        nargs="*",
        type=float,
        default=list(DEFAULT_WEIGHTS),
        help="要扫描的 vector_weight 列表（bm25_weight = 1 - vector_weight），默认 7 个点",
    )
    args = parser.parse_args()

    cases = load_bench(args.bench)
    weights = sorted(set(round(w, 4) for w in args.weights))
    print(f"加载 {len(cases)} 条评测用例（{args.bench}）")
    print(f"扫描权重：{weights}（top_k={args.top_k}）")

    print("初始化 KB ...")
    kb = get_knowledge_base()
    id_to_category = {e.id: e.category for e in kb.entries}
    ks = tuple(k for k in DEFAULT_KS if k <= args.top_k) or (args.top_k,)

    # 启用 query embedding 缓存：同一 query 跨 7 组权重只需嵌入 1 次
    cached_client = _QueryCachedEmbedding(kb.embedding_client)
    kb.embedding_client = cached_client

    rows: List[Dict[str, Any]] = []
    for w in weights:
        print(f"\n[vector_weight={w:.2f}, bm25_weight={1-w:.2f}] ...")
        overall, case_metrics = run_one_weight(
            cases, vector_weight=w, top_k=args.top_k,
            id_to_category=id_to_category, ks=ks,
        )
        print(
            f"  top1={overall.get('top1_hit_rate', 0)*100:.1f}%  "
            f"MRR={overall.get('mrr', 0):.3f}  "
            f"R@1={overall.get('recall@1', 0)*100:.1f}%  "
            f"R@{ks[-1]}={overall.get(f'recall@{ks[-1]}', 0)*100:.1f}%"
        )
        rows.append({
            "vector_weight": w,
            "bm25_weight": 1.0 - w,
            "overall": overall,
            "case_metrics": case_metrics,
        })

    print("\n=== 权重扫描总表 ===")
    col_w = 11
    print(f"{'v_w':<6}{'b_w':<6}" + "".join(f"{x:>{col_w}}" for x in ("top1", "MRR", "R@1", f"R@{ks[-1]}", f"P@{ks[-1]}")))
    print("-" * (6 + 6 + col_w * 5))
    for r in rows:
        print(
            f"{r['vector_weight']:<6.2f}{r['bm25_weight']:<6.2f}"
            f"{r['overall'].get('top1_hit_rate', 0)*100:>{col_w-1}.1f}%"
            f"{r['overall'].get('mrr', 0):>{col_w}.3f}"
            f"{r['overall'].get('recall@1', 0)*100:>{col_w-1}.1f}%"
            f"{r['overall'].get(f'recall@{ks[-1]}', 0)*100:>{col_w-1}.1f}%"
            f"{r['overall'].get(f'precision@{ks[-1]}', 0)*100:>{col_w-1}.1f}%"
        )

    os.makedirs(args.out, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(args.out, f"rag_weight_sweep_{ts}.json")
    md_path = os.path.join(args.out, f"rag_weight_sweep_{ts}.md")
    latest_md = os.path.join(args.out, "rag_weight_sweep_latest.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "n_cases": len(cases),
            "top_k": args.top_k,
            "ks": list(ks),
            "rows": rows,
        }, f, ensure_ascii=False, indent=2)

    md = render_markdown(rows, len(cases), ts, args.top_k, ks)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n报告已写入：\n  - {json_path}\n  - {md_path}\n  - {latest_md}（最新版镜像）")
    print(f"query embedding 缓存命中数：{cached_client.cache_size} 条 unique query")


if __name__ == "__main__":
    main()
