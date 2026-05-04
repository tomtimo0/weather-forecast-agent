"""通路 A（search_knowledge）检索质量评测：3 档检索器消融对比

跑 ``data/test_cases/rag_retrieval_bench.jsonl`` 中的所有 query，对每条
query 分别用 ``vector`` / ``bm25`` / ``hybrid`` 三档检索器评测 Top-K 表现，
对应论文中"为什么必须采用混合检索"的实证。

输出：
1. 控制台：3 档总表 + 按 category 拆分表
2. ``experiments/results/rag_retrieval_eval_<timestamp>.json``：原始结果
3. ``experiments/results/rag_retrieval_eval_<timestamp>.md``：论文友好的 Markdown 报告

用法：
    python -m experiments.eval.run_rag_eval

可选参数：
    --bench    评测集 JSONL 路径
    --out      结果输出目录
    --top-k    每档检索器返回的 K 值（默认 5）
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List, Sequence, Tuple

from experiments.eval.retrieval_metrics import (
    aggregate,
    aggregate_by_category,
    evaluate_case,
    load_bench,
)
from src.rag.knowledge_base import get_knowledge_base
from src.rag.retriever import get_retriever


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_BENCH = os.path.join(PROJECT_ROOT, "data", "test_cases", "rag_retrieval_bench.jsonl")
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "experiments", "results")
DEFAULT_KS: Tuple[int, ...] = (1, 3, 5)
DEFAULT_MODES: Tuple[str, ...] = ("vector", "bm25", "hybrid")


def _retrieve(mode: str, query: str, top_k: int) -> List[str]:
    """统一接口：返回检索器对 query 给出的 top-K 条目 ID（按分数降序）。"""
    if mode == "vector":
        kb = get_knowledge_base()
        hits = kb.vector_search(query, top_k=top_k)
        return [entry.id for entry, _ in hits]
    if mode == "bm25":
        kb = get_knowledge_base()
        hits = kb.bm25_search(query, top_k=top_k)
        return [entry.id for entry, _ in hits]
    if mode == "hybrid":
        retriever = get_retriever()
        hits = retriever.retrieve(query, top_k=top_k)
        return [hit.entry.id for hit in hits]
    raise ValueError(f"未知检索模式：{mode}")


def _build_id_to_category() -> Dict[str, str]:
    """构建 KB 中 id → category 映射，用于 Category@K 指标。"""
    kb = get_knowledge_base()
    return {e.id: e.category for e in kb.entries}


def run_one_mode(
    cases: List[Dict[str, Any]],
    mode: str,
    top_k: int,
    id_to_category: Dict[str, str],
    ks: Sequence[int],
    show_progress: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """对所有用例在指定 mode 下跑一遍，返回 (case_metrics, failures) 二元组。

    failure 定义：top1_hit=False 即 top-1 没命中任何相关条目。
    """
    case_results: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    n = len(cases)
    for idx, case in enumerate(cases, 1):
        predicted_ids = _retrieve(mode, case["query"], top_k=top_k)
        if show_progress:
            tag = "命中" if predicted_ids and predicted_ids[0] in case.get("relevant_ids", []) else "脱靶"
            print(f"  [{mode}] {idx:>2}/{n} {tag} {case['id']}")
        m = evaluate_case(case, predicted_ids, id_to_category, ks=ks)
        m["predicted_top_k"] = predicted_ids
        case_results.append(m)
        if not m["top1_hit"]:
            failures.append({
                "id": case["id"],
                "category": case.get("category"),
                "description": case.get("description", ""),
                "query": case["query"],
                "relevant_ids": case.get("relevant_ids", []),
                "predicted_top_k": predicted_ids,
                "metrics": {k: m[k] for k in m if k.startswith(("recall@", "category@", "precision@")) or k in ("mrr", "top1_hit")},
            })
    return case_results, failures


def render_markdown(
    overall: Dict[str, Dict[str, Any]],
    by_cat: Dict[str, Dict[str, Dict[str, Any]]],
    failures: Dict[str, List[Dict[str, Any]]],
    n_cases: int,
    timestamp: str,
    modes: Tuple[str, ...],
    ks: Sequence[int],
    top_k: int,
) -> str:
    """渲染论文可用的 Markdown 报告。"""
    out: List[str] = []
    out.append("# 通路 A（RAG 检索）评测报告")
    out.append("")
    out.append(f"- 评测时间：{timestamp}")
    out.append(f"- 用例总数：**{n_cases}**")
    out.append(f"- 评测档位：{', '.join(modes)}")
    out.append(f"- 每档返回 Top-K：{top_k}（统计 K={list(ks)}）")
    out.append(f"- 评测集：`data/test_cases/rag_retrieval_bench.jsonl`")
    out.append("")

    # ---------- 一、3 档消融总表 ----------
    out.append(f"## 一、{len(modes)} 档检索器消融总表")
    out.append("")
    header = "| 指标 |" + "".join(f" mode={m} |" for m in modes)
    sep = "|---|" + "---|" * len(modes)
    out.append(header)
    out.append(sep)

    metric_rows: List[Tuple[str, str, str]] = [
        ("Top-1 命中率（top1_hit_rate）", "top1_hit_rate", "ratio"),
        ("MRR（首个相关条目排名倒数）", "mrr", "ratio"),
    ]
    for k in ks:
        metric_rows.append((f"Recall@{k}", f"recall@{k}", "pct"))
    for k in ks:
        metric_rows.append((f"Precision@{k}", f"precision@{k}", "pct"))
    for k in ks:
        metric_rows.append((f"Category@{k}（类别一致率）", f"category@{k}", "pct"))

    for label, key, fmt in metric_rows:
        cells = [label]
        for mode in modes:
            v = overall[mode].get(key)
            if v is None:
                cells.append("—")
            elif fmt == "pct":
                cells.append(f"{v * 100:.1f}%")
            else:
                cells.append(f"{v:.3f}")
        out.append("| " + " | ".join(cells) + " |")
    out.append("")

    # ---------- 二、按 query 类别拆分（Recall@5） ----------
    out.append(f"## 二、按用例类别拆分（Recall@{ks[-1]}）")
    out.append("")
    cats = sorted({c for mode_cat in by_cat.values() for c in mode_cat})
    header2 = "| 类别 | 用例数 |" + "".join(f" {m} · Recall@{ks[-1]} |" for m in modes)
    out.append(header2)
    out.append("|---|---|" + "---|" * len(modes))
    base_mode = modes[0]
    for cat in cats:
        n = by_cat[base_mode].get(cat, {}).get("n_cases", 0)
        cells = [cat, str(n)]
        for m in modes:
            r = by_cat[m].get(cat, {}).get(f"recall@{ks[-1]}")
            cells.append("—" if r is None else f"{r * 100:.1f}%")
        out.append("| " + " | ".join(cells) + " |")
    out.append("")

    # ---------- 三、按类别 top1_hit_rate 拆分 ----------
    out.append("## 三、按用例类别拆分（Top-1 命中率）")
    out.append("")
    out.append("| 类别 | 用例数 |" + "".join(f" {m} · top1 |" for m in modes))
    out.append("|---|---|" + "---|" * len(modes))
    for cat in cats:
        n = by_cat[base_mode].get(cat, {}).get("n_cases", 0)
        cells = [cat, str(n)]
        for m in modes:
            t = by_cat[m].get(cat, {}).get("top1_hit_rate")
            cells.append("—" if t is None else f"{t * 100:.1f}%")
        out.append("| " + " | ".join(cells) + " |")
    out.append("")

    # ---------- 四、失败用例（top-1 脱靶） ----------
    out.append("## 四、失败用例（top-1 未命中相关条目）")
    out.append("")
    for mode in modes:
        flist = failures.get(mode, [])
        if not flist:
            out.append(f"### mode={mode}：无失败用例")
            out.append("")
            continue
        out.append(f"### mode={mode}（{len(flist)} 条）")
        out.append("")
        for f in flist:
            out.append(f"- **{f['id']}** [{f['category']}] {f['description']}")
            out.append(f"  - query: `{f['query']}`")
            out.append(f"  - 期望相关 ids: `{f['relevant_ids']}`")
            out.append(f"  - 实际 top-{top_k}: `{f['predicted_top_k']}`")
            out.append(
                "  - 指标："
                + ", ".join(
                    f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                    for k, v in f["metrics"].items()
                    if v is not None
                )
            )
            out.append("")

    # ---------- 五、关键结论 ----------
    out.append("## 五、关键结论（自动摘要）")
    out.append("")
    if "vector" in overall and "bm25" in overall and "hybrid" in overall:
        v_recall = overall["vector"].get(f"recall@{ks[-1]}") or 0
        b_recall = overall["bm25"].get(f"recall@{ks[-1]}") or 0
        h_recall = overall["hybrid"].get(f"recall@{ks[-1]}") or 0
        v_top1 = overall["vector"].get("top1_hit_rate") or 0
        b_top1 = overall["bm25"].get("top1_hit_rate") or 0
        h_top1 = overall["hybrid"].get("top1_hit_rate") or 0
        v_mrr = overall["vector"].get("mrr") or 0
        b_mrr = overall["bm25"].get("mrr") or 0
        h_mrr = overall["hybrid"].get("mrr") or 0
        out.append(
            f"- **混合检索的边际增益**：Recall@{ks[-1]} 上 hybrid={h_recall * 100:.1f}% "
            f"vs vector={v_recall * 100:.1f}% / bm25={b_recall * 100:.1f}%；"
            f"MRR 上 hybrid={h_mrr:.3f} vs vector={v_mrr:.3f} / bm25={b_mrr:.3f}。"
        )
        out.append(
            f"- **Top-1 命中率**：hybrid={h_top1 * 100:.1f}% vs "
            f"vector={v_top1 * 100:.1f}% / bm25={b_top1 * 100:.1f}%，"
            "反映实际作为 LLM 上下文最重要的「第一引用项」准确度。"
        )
        if h_recall >= max(v_recall, b_recall) - 1e-6:
            out.append(
                "- 结论：混合检索在 Recall 上不弱于任一单路，"
                "且通常优于纯向量（处理「清劲风/疾风」等专有名词时 BM25 路径补足）"
                "或纯 BM25（处理「打雷怎么应对」等同义改写时向量路径补足），"
                "支持论文中混合检索的设计选择。"
            )
    out.append("")

    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="通路 A（RAG 检索）3 档消融评测")
    parser.add_argument("--bench", default=DEFAULT_BENCH, help="评测集 JSONL 路径")
    parser.add_argument("--out", default=DEFAULT_OUT, help="结果输出目录")
    parser.add_argument("--top-k", type=int, default=5, help="每档检索器返回的 K 值（默认 5）")
    args = parser.parse_args()

    cases = load_bench(args.bench)
    print(f"加载 {len(cases)} 条评测用例（{args.bench}）")
    print(f"评测档位：{DEFAULT_MODES}（top_k={args.top_k}）")

    print("初始化 KB / 检索器 ...")
    id_to_category = _build_id_to_category()
    get_retriever()

    ks = tuple(k for k in DEFAULT_KS if k <= args.top_k) or (args.top_k,)

    all_case_metrics: Dict[str, List[Dict[str, Any]]] = {}
    all_failures: Dict[str, List[Dict[str, Any]]] = {}
    for mode in DEFAULT_MODES:
        print(f"\n[mode={mode}] 开始")
        case_metrics, failures = run_one_mode(
            cases, mode, top_k=args.top_k,
            id_to_category=id_to_category, ks=ks,
            show_progress=False,
        )
        all_case_metrics[mode] = case_metrics
        all_failures[mode] = failures

    overall = {mode: aggregate(all_case_metrics[mode], ks=ks) for mode in DEFAULT_MODES}
    by_cat = {mode: aggregate_by_category(all_case_metrics[mode], ks=ks) for mode in DEFAULT_MODES}

    print(f"\n=== {len(DEFAULT_MODES)} 档检索器总表 ===")
    col_w = 12
    header_cells = [f"{'指标':<22}"] + [f"{m:>{col_w}}" for m in DEFAULT_MODES]
    print(" ".join(header_cells))
    print("-" * (22 + (col_w + 1) * len(DEFAULT_MODES)))
    rows: List[Tuple[str, str, str]] = [
        ("Top-1 命中率", "top1_hit_rate", "pct"),
        ("MRR", "mrr", "raw"),
    ]
    for k in ks:
        rows.append((f"Recall@{k}", f"recall@{k}", "pct"))
    for k in ks:
        rows.append((f"Precision@{k}", f"precision@{k}", "pct"))
    for k in ks:
        rows.append((f"Category@{k}", f"category@{k}", "pct"))

    for label, key, fmt in rows:
        formatted: List[str] = []
        for m in DEFAULT_MODES:
            v = overall[m].get(key)
            if v is None:
                formatted.append(f"{'—':>{col_w}}")
            elif fmt == "pct":
                formatted.append(f"{v * 100:>{col_w - 1}.1f}%")
            else:
                formatted.append(f"{v:>{col_w}.3f}")
        print(f"{label:<22}" + " ".join(formatted))

    print(f"\n失败用例（top-1 脱靶）汇总：")
    for mode in DEFAULT_MODES:
        print(f"  · {mode}: {len(all_failures[mode])} 条")

    os.makedirs(args.out, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(args.out, f"rag_retrieval_eval_{ts}.json")
    md_path = os.path.join(args.out, f"rag_retrieval_eval_{ts}.md")
    latest_md = os.path.join(args.out, "rag_retrieval_eval_latest.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "n_cases": len(cases),
            "top_k": args.top_k,
            "ks": list(ks),
            "modes": list(DEFAULT_MODES),
            "overall": overall,
            "by_category": by_cat,
            "case_metrics": all_case_metrics,
            "failures": all_failures,
        }, f, ensure_ascii=False, indent=2)

    md = render_markdown(overall, by_cat, all_failures, len(cases), ts, DEFAULT_MODES, ks, args.top_k)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n报告已写入：\n  - {json_path}\n  - {md_path}\n  - {latest_md}（最新版镜像）")


if __name__ == "__main__":
    main()
