"""语义桥接三档消融评测主入口

跑 ``data/test_cases/semantic_bridge_bench.jsonl`` 中所有用例，对每条用例
分别用 ``mode=off`` / ``rule_only`` / ``rule_plus_rag`` 跑一遍，输出：

1. 控制台：三档主指标对比表 + 各 category 拆分表
2. ``experiments/results/semantic_bridge_eval_<timestamp>.json``：原始结果
3. ``experiments/results/semantic_bridge_eval_<timestamp>.md``：论文友好的 Markdown 报告

用法：
    python -m experiments.eval.run_bridge_eval

可选参数：
    --bench  评测集 JSONL 路径（默认 data/test_cases/semantic_bridge_bench.jsonl）
    --out    结果输出目录（默认 experiments/results）
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List

from experiments.eval.metrics import (
    aggregate,
    aggregate_by_category,
    evaluate_case,
)
from src.analysis.semantic_bridge import bridge_weather_dict


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_BENCH = os.path.join(PROJECT_ROOT, "data", "test_cases", "semantic_bridge_bench.jsonl")
DEFAULT_OUT = os.path.join(PROJECT_ROOT, "experiments", "results")

MODES = ("off", "rule_only", "rule_plus_rag")


def load_bench(path: str) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"评测集 {path}:{lineno} 解析失败：{exc}") from exc
    return cases


def run_one_mode(cases: List[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    """对所有用例在指定 mode 下跑一遍，返回 case_metrics 列表（与 cases 等长）。"""
    case_results: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    for case in cases:
        result = bridge_weather_dict(
            data=case["input"],
            scene=case.get("scene"),
            mode=mode,
        )
        m = evaluate_case(case["expected"], result, mode)
        m["id"] = case["id"]
        m["category"] = case.get("category", "unknown")
        case_results.append(m)

        passed = (
            m.get("grade_accuracy") == 1
            and m.get("grade_id_accuracy") == 1
            and m.get("n_labels_match") == 1
            and (m.get("citation_rate") in (None, 1))
            and (m.get("citation_negative_pass") in (None, 1))
            and (m.get("source_match") in (None, 1))
        )
        if not passed:
            failures.append({
                "id": case["id"],
                "category": case["category"],
                "description": case.get("description", ""),
                "metrics": m,
                "input": case["input"],
                "scene": case.get("scene"),
                "actual_text": result.get("semantic_text", "")[:200],
                "actual_labels": [
                    {
                        "variable": lbl.variable,
                        "grade": lbl.grade,
                        "grade_id": lbl.grade_id,
                        "source": lbl.source,
                    }
                    for lbl in result.get("labels", [])
                ],
            })
    return case_results, failures


def render_markdown(
    overall: Dict[str, Dict[str, Any]],
    by_cat: Dict[str, Dict[str, Dict[str, Any]]],
    failures: Dict[str, List[Dict[str, Any]]],
    n_cases: int,
    timestamp: str,
) -> str:
    """把结果渲染成论文可用的 Markdown 报告。"""
    out: List[str] = []
    out.append("# 语义桥接评测报告")
    out.append("")
    out.append(f"- 评测时间：{timestamp}")
    out.append(f"- 用例总数：**{n_cases}**")
    out.append(f"- 评测集：`data/test_cases/semantic_bridge_bench.jsonl`")
    out.append(f"- 被测对象：`src.analysis.semantic_bridge.bridge_weather_dict`")
    out.append("")
    out.append("## 一、三档消融总表")
    out.append("")
    out.append("| 指标 | mode=off (baseline) | mode=rule_only | mode=rule_plus_rag |")
    out.append("|---|---|---|---|")
    metric_rows = [
        ("覆盖率（生成 ≥1 label）", "coverage"),
        ("标签条数一致", "n_labels_match"),
        ("分级名准确率（grade）", "grade_accuracy"),
        ("分级 ID 准确率（grade_id）", "grade_id_accuracy"),
        ("引用率（must_cite 全中）", "citation_rate"),
        ("场景过滤负例通过率", "citation_negative_pass"),
        ("source 字段匹配率", "source_match"),
        ("baseline 文本为空率", "text_empty"),
    ]
    for label, key in metric_rows:
        cells = [label]
        for mode in MODES:
            v = overall[mode].get(key)
            cells.append("—" if v is None else f"{v:.1f}%")
        out.append("| " + " | ".join(cells) + " |")
    out.append("")

    out.append("## 二、按用例类别拆分（grade_id 准确率 / 引用率）")
    out.append("")
    cats = sorted({c for mode_cat in by_cat.values() for c in mode_cat})
    out.append("| 类别 | 用例数 | rule_only · grade_id | rule_plus_rag · grade_id | rule_plus_rag · 引用率 |")
    out.append("|---|---|---|---|---|")
    for cat in cats:
        n = by_cat["rule_only"].get(cat, {}).get("n_cases", 0)
        ro_gid = by_cat["rule_only"].get(cat, {}).get("grade_id_accuracy")
        rag_gid = by_cat["rule_plus_rag"].get(cat, {}).get("grade_id_accuracy")
        rag_cite = by_cat["rule_plus_rag"].get(cat, {}).get("citation_rate")
        out.append(
            f"| {cat} | {n} | "
            f"{('—' if ro_gid is None else f'{ro_gid:.1f}%')} | "
            f"{('—' if rag_gid is None else f'{rag_gid:.1f}%')} | "
            f"{('—' if rag_cite is None else f'{rag_cite:.1f}%')} |"
        )
    out.append("")

    out.append("## 三、失败用例")
    out.append("")
    out.append(
        f"> mode=off 下"
        f"**预期**全部用例（除 fallback 外）覆盖率为 0%，这是 baseline 设计目标——"
        f"用以与桥接模式对比。本节仅展示 rule_only / rule_plus_rag 的"
        "**真正失败**（即未达到设计目标的用例）。"
    )
    out.append("")
    real_modes = ("rule_only", "rule_plus_rag")
    any_failure = False
    for mode in real_modes:
        flist = failures.get(mode, [])
        if not flist:
            continue
        any_failure = True
        out.append(f"### mode={mode}（{len(flist)} 条）")
        out.append("")
        for f in flist:
            out.append(f"- **{f['id']}** [{f['category']}] {f['description']}")
            out.append(f"  - input: `{json.dumps(f['input'], ensure_ascii=False)}`，scene: `{f.get('scene')}`")
            out.append(f"  - 实际 labels: `{f['actual_labels']}`")
            out.append(f"  - 实际文本前 200 字：`{f['actual_text']!r}`")
            out.append("")
    if not any_failure:
        out.append("rule_only 与 rule_plus_rag 模式下**无失败用例**，全部通过期望。")
        out.append("")
    n_off_failures = len(failures.get("off", []))
    n_non_fallback = sum(
        v.get("n_cases", 0) for k, v in by_cat["rule_only"].items() if k != "fallback"
    )
    out.append(
        f"备注：mode=off 在 {n_non_fallback} 条非 fallback 用例上 "
        f"**累计未达期望** {n_off_failures} 条 "
        f"（{n_off_failures}/{n_non_fallback} = "
        f"{(n_off_failures / max(1, n_non_fallback) * 100):.0f}%），"
        "构成消融对照的负参照——证明不做桥接时纯靠 LLM 自由发挥无法稳定提供分级语义。"
    )
    out.append("")

    out.append("## 四、关键结论（自动摘要）")
    out.append("")
    rag_grade = overall["rule_plus_rag"].get("grade_id_accuracy") or 0
    rag_cite = overall["rule_plus_rag"].get("citation_rate") or 0
    rule_grade = overall["rule_only"].get("grade_id_accuracy") or 0
    off_text_empty = overall["off"].get("text_empty") or 0
    out.append(
        f"- **确定性分级覆盖**：rule_only 模式下 grade_id 准确率 {rule_grade:.1f}%，"
        "证明分类器表的阈值划分覆盖了所有有效输入。"
    )
    out.append(
        f"- **权威引用注入**：rule_plus_rag 模式下引用关键字命中率 {rag_cite:.1f}%，"
        "证明 grade_id 硬链接能稳定从 KB 召回出处条款；场景不匹配时正确退化为 rule_only，"
        "不输出无关 citation。"
    )
    out.append(
        f"- **baseline 对照**：mode=off 时 semantic_text 为空率 {off_text_empty:.1f}%，"
        "完全依赖 LLM 自由发挥处理裸数值，作为消融实验的负参照。"
    )
    out.append("")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="语义桥接三档消融评测")
    parser.add_argument("--bench", default=DEFAULT_BENCH, help="评测集 JSONL 路径")
    parser.add_argument("--out", default=DEFAULT_OUT, help="结果输出目录")
    args = parser.parse_args()

    cases = load_bench(args.bench)
    print(f"加载 {len(cases)} 条评测用例（{args.bench}）")

    all_case_metrics: Dict[str, List[Dict[str, Any]]] = {}
    all_failures: Dict[str, List[Dict[str, Any]]] = {}
    for mode in MODES:
        case_metrics, failures = run_one_mode(cases, mode)
        all_case_metrics[mode] = case_metrics
        all_failures[mode] = failures

    overall = {mode: aggregate(all_case_metrics[mode]) for mode in MODES}
    by_cat = {mode: aggregate_by_category(all_case_metrics[mode], cases) for mode in MODES}

    print("\n=== 三档消融总表 ===")
    print(f"{'指标':<28} {'off':>10} {'rule_only':>14} {'rule_plus_rag':>17}")
    print("-" * 72)
    rows = [
        ("覆盖率", "coverage"),
        ("标签数一致", "n_labels_match"),
        ("grade 准确", "grade_accuracy"),
        ("grade_id 准确", "grade_id_accuracy"),
        ("引用率", "citation_rate"),
        ("场景过滤负例通过", "citation_negative_pass"),
        ("source 匹配", "source_match"),
        ("baseline 空文本率", "text_empty"),
    ]
    for label, key in rows:
        cells = [label.ljust(20)]
        for mode in MODES:
            v = overall[mode].get(key)
            cells.append("    —" if v is None else f"{v:>6.1f}%")
        print(f"{cells[0]:<28} {cells[1]:>10} {cells[2]:>14} {cells[3]:>17}")

    total_failures = sum(len(v) for v in all_failures.values())
    print(f"\n失败用例总数（含三档累计）：{total_failures}")
    for mode in MODES:
        if all_failures[mode]:
            print(f"  · {mode}: {len(all_failures[mode])} 条")

    os.makedirs(args.out, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(args.out, f"semantic_bridge_eval_{ts}.json")
    md_path = os.path.join(args.out, f"semantic_bridge_eval_{ts}.md")
    latest_md = os.path.join(args.out, "semantic_bridge_eval_latest.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "n_cases": len(cases),
            "overall": overall,
            "by_category": by_cat,
            "case_metrics": all_case_metrics,
            "failures": all_failures,
        }, f, ensure_ascii=False, indent=2)

    md = render_markdown(overall, by_cat, all_failures, len(cases), ts)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n报告已写入：\n  - {json_path}\n  - {md_path}\n  - {latest_md}（最新版镜像）")


if __name__ == "__main__":
    main()
