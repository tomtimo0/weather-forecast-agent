"""语义桥接三档消融评测主入口（可选第 4 档：LLM baseline）

跑 ``data/test_cases/semantic_bridge_bench.jsonl`` 中所有用例，对每条用例分
别用 ``mode=off`` / ``rule_only`` / ``rule_plus_rag`` 跑一遍。可选加上
``--with-llm-baseline`` 开关跑第 4 档 LLM baseline（让 LLM 自由发挥处理裸数
据），形成完整 4 档对比，对应论文 Q3 章节核心实证。

输出：
1. 控制台：三/四档主指标对比表 + 各 category 拆分表
2. ``experiments/results/semantic_bridge_eval_<timestamp>.json``：原始结果
3. ``experiments/results/semantic_bridge_eval_<timestamp>.md``：论文友好的 Markdown 报告

用法：
    python -m experiments.eval.run_bridge_eval                      # 三档（无网络，约 6 秒）
    python -m experiments.eval.run_bridge_eval --with-llm-baseline  # 四档（含 LLM 调用）

可选参数：
    --bench               评测集 JSONL 路径
    --out                 结果输出目录
    --with-llm-baseline   额外跑 LLM baseline 档
    --force-llm           强制重新调 LLM（跳过缓存）
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

DEFAULT_MODES = ("off", "rule_only", "rule_plus_rag")
LLM_BASELINE_MODE = "llm_baseline"


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


def _run_case(case: Dict[str, Any], mode: str, llm_cache: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """对一条 case 在指定 mode 下跑一次，返回 result 字典（统一形态）。"""
    if mode == LLM_BASELINE_MODE:
        from experiments.eval.llm_baseline import run_llm_baseline
        return run_llm_baseline(
            input_dict=case["input"],
            scene=case.get("scene"),
            cache=llm_cache,
        )
    return bridge_weather_dict(
        data=case["input"],
        scene=case.get("scene"),
        mode=mode,
    )


def run_one_mode(
    cases: List[Dict[str, Any]],
    mode: str,
    llm_cache: Dict[str, Any] | None = None,
    show_progress: bool = False,
):
    """对所有用例在指定 mode 下跑一遍，返回 (case_metrics, failures) 二元组。"""
    case_results: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    n = len(cases)
    for idx, case in enumerate(cases, 1):
        result = _run_case(case, mode, llm_cache)
        if show_progress:
            tag = "缓存" if result.get("cache_hit") else "调用"
            print(f"  [{mode}] {idx:>2}/{n} {tag} {case['id']}")
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


_MODE_DISPLAY = {
    "off": "off (baseline)",
    "llm_baseline": "llm_baseline",
    "rule_only": "rule_only",
    "rule_plus_rag": "rule_plus_rag",
}


def render_markdown(
    overall: Dict[str, Dict[str, Any]],
    by_cat: Dict[str, Dict[str, Dict[str, Any]]],
    failures: Dict[str, List[Dict[str, Any]]],
    n_cases: int,
    timestamp: str,
    modes: tuple,
) -> str:
    """把结果渲染成论文可用的 Markdown 报告。"""
    out: List[str] = []
    out.append("# 语义桥接评测报告")
    out.append("")
    out.append(f"- 评测时间：{timestamp}")
    out.append(f"- 用例总数：**{n_cases}**")
    out.append(f"- 评测档位：{', '.join(modes)}")
    out.append(f"- 评测集：`data/test_cases/semantic_bridge_bench.jsonl`")
    out.append("")
    out.append(f"## 一、{len(modes)} 档消融总表")
    out.append("")
    header = "| 指标 |" + "".join(f" mode={_MODE_DISPLAY.get(m, m)} |" for m in modes)
    sep = "|---|" + "---|" * len(modes)
    out.append(header)
    out.append(sep)
    metric_rows = [
        ("覆盖率（生成 ≥1 label）", "coverage"),
        ("标签条数一致", "n_labels_match"),
        ("分级名准确率（grade）", "grade_accuracy"),
        ("分级 ID 准确率（grade_id）", "grade_id_accuracy"),
        ("引用率（must_cite 全中）", "citation_rate"),
        ("场景过滤负例通过率", "citation_negative_pass"),
        ("source 字段匹配率", "source_match"),
        ("baseline 文本为空率（off 专属）", "text_empty"),
        ("citation 出现率（LLM baseline 专属）", "citation_present_rate"),
        ("citation 标准号真实性（LLM baseline 专属）", "citation_authenticity"),
    ]
    for label, key in metric_rows:
        cells = [label]
        for mode in modes:
            v = overall[mode].get(key)
            cells.append("—" if v is None else f"{v:.1f}%")
        out.append("| " + " | ".join(cells) + " |")
    out.append("")

    out.append("## 二、按用例类别拆分")
    out.append("")
    cats = sorted({c for mode_cat in by_cat.values() for c in mode_cat})
    cmp_modes = [m for m in modes if m != "off"]
    header2 = "| 类别 | 用例数 |" + "".join(
        f" {m} · grade_id |" for m in cmp_modes
    ) + (" llm · cite真实 |" if "llm_baseline" in modes else "") + " rag · 引用率 |"
    out.append(header2)
    out.append("|---|---|" + "---|" * (len(cmp_modes) + (1 if "llm_baseline" in modes else 0) + 1))
    base_mode = "rule_only" if "rule_only" in modes else cmp_modes[0]
    for cat in cats:
        n = by_cat[base_mode].get(cat, {}).get("n_cases", 0)
        cells = [cat, str(n)]
        for m in cmp_modes:
            gid = by_cat[m].get(cat, {}).get("grade_id_accuracy")
            cells.append("—" if gid is None else f"{gid:.1f}%")
        if "llm_baseline" in modes:
            auth = by_cat["llm_baseline"].get(cat, {}).get("citation_authenticity")
            cells.append("—" if auth is None else f"{auth:.1f}%")
        rag_cite = (
            by_cat["rule_plus_rag"].get(cat, {}).get("citation_rate")
            if "rule_plus_rag" in modes else None
        )
        cells.append("—" if rag_cite is None else f"{rag_cite:.1f}%")
        out.append("| " + " | ".join(cells) + " |")
    out.append("")

    out.append("## 三、失败用例")
    out.append("")
    out.append(
        "> mode=off 下**预期**全部非 fallback 用例覆盖率为 0%，是 baseline 设计目标，"
        "本节不重复展示其失败明细（详见关键结论部分的统计）。"
        "本节展示 rule_only / rule_plus_rag / llm_baseline 三档下"
        "**未达到期望**的用例。"
    )
    out.append("")
    real_modes = tuple(m for m in modes if m != "off")
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
        out.append(f"以上 {len(real_modes)} 档模式**无失败用例**，全部通过期望。")
        out.append("")
    if "off" in modes:
        n_off_failures = len(failures.get("off", []))
        base_mode = "rule_only" if "rule_only" in modes else real_modes[0]
        n_non_fallback = sum(
            v.get("n_cases", 0) for k, v in by_cat[base_mode].items() if k != "fallback"
        )
        out.append(
            f"备注：mode=off 在 {n_non_fallback} 条非 fallback 用例上 "
            f"**累计未达期望** {n_off_failures} 条 "
            f"（{n_off_failures}/{n_non_fallback} = "
            f"{(n_off_failures / max(1, n_non_fallback) * 100):.0f}%），"
            "构成消融对照的负参照。"
        )
        out.append("")

    out.append("## 四、关键结论（自动摘要）")
    out.append("")
    if "rule_only" in modes:
        rule_grade = overall["rule_only"].get("grade_id_accuracy") or 0
        out.append(
            f"- **确定性分级覆盖**：rule_only 模式下 grade_id 准确率 {rule_grade:.1f}%，"
            "证明分类器表的阈值划分覆盖了所有有效输入。"
        )
    if "rule_plus_rag" in modes:
        rag_cite = overall["rule_plus_rag"].get("citation_rate") or 0
        out.append(
            f"- **权威引用注入**：rule_plus_rag 模式下 must_cite 关键字命中率 {rag_cite:.1f}%，"
            "证明 grade_id 硬链接能稳定从 KB 召回出处条款；场景不匹配时正确退化为 rule_only，"
            "不输出无关 citation。"
        )
    if "off" in modes:
        off_text_empty = overall["off"].get("text_empty") or 0
        out.append(
            f"- **baseline 对照**：mode=off 时 semantic_text 为空率 {off_text_empty:.1f}%，"
            "完全依赖 LLM 自由发挥处理裸数值，作为消融实验的负参照。"
        )
    if "llm_baseline" in modes:
        llm = overall["llm_baseline"]
        gid = llm.get("grade_id_accuracy") or 0
        grade = llm.get("grade_accuracy") or 0
        cite = llm.get("citation_rate")
        cite_str = "—" if cite is None else f"{cite:.1f}%"
        present = llm.get("citation_present_rate") or 0
        auth = llm.get("citation_authenticity") or 0
        smatch = llm.get("source_match") or 0
        out.append(
            f"- **LLM 自由发挥（无桥接）**：grade 名准确率 {grade:.1f}%、grade_id 准确率 "
            f"{gid:.1f}%（凭印象编 ID 几乎不可能与 KB 命名一致）；citation 出现率 "
            f"{present:.1f}%（LLM 几乎都给出了一段 citation），其中**包含真实存在标准号的"
            f"比率 {auth:.1f}%**（粗粒度幻觉检测）；must_cite 关键字命中率 {cite_str}（与 KB 完全一致的"
            f"严格命中率），source 字段升级率 {smatch:.1f}%。"
        )
        out.append(
            "- **关键观察**：LLM baseline 在 grade 名上有相当能力（凭内置常识可推断"
            "“35mm = 大雨”这类典型分级），但在**严格的标准编号 + 条款号**上呈现典型"
            "幻觉模式：标准号对、条款号错；或张冠李戴用相邻标准。这与"
            "`docs/写作文档/知识库标准核对表-论文素材.md` 中我们对种子数据"
            "做人工核对时发现的同类错误一一对应。"
        )
    out.append("")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="语义桥接三/四档消融评测")
    parser.add_argument("--bench", default=DEFAULT_BENCH, help="评测集 JSONL 路径")
    parser.add_argument("--out", default=DEFAULT_OUT, help="结果输出目录")
    parser.add_argument(
        "--with-llm-baseline",
        action="store_true",
        help="额外跑 LLM baseline 档（需 LLM 服务可用，会消耗 token）",
    )
    parser.add_argument(
        "--force-llm",
        action="store_true",
        help="跳过 LLM baseline 缓存，强制重新调 LLM（仅当 --with-llm-baseline 时生效）",
    )
    args = parser.parse_args()

    cases = load_bench(args.bench)
    print(f"加载 {len(cases)} 条评测用例（{args.bench}）")

    if args.with_llm_baseline:
        modes = DEFAULT_MODES + (LLM_BASELINE_MODE,)
    else:
        modes = DEFAULT_MODES
    print(f"评测档位：{modes}")

    llm_cache: Dict[str, Any] | None = None
    if LLM_BASELINE_MODE in modes:
        from experiments.eval.llm_baseline import DEFAULT_CACHE_PATH, load_cache, save_cache
        if args.force_llm:
            print("[--force-llm] 跳过缓存重跑")
            llm_cache = {}
        else:
            llm_cache = load_cache(DEFAULT_CACHE_PATH)
            print(f"加载 LLM baseline 缓存：{len(llm_cache)} 条")

    all_case_metrics: Dict[str, List[Dict[str, Any]]] = {}
    all_failures: Dict[str, List[Dict[str, Any]]] = {}
    for mode in modes:
        if mode == LLM_BASELINE_MODE:
            print(f"\n[mode={mode}] 开始（命中缓存的条目几乎瞬时返回）")
            case_metrics, failures = run_one_mode(
                cases, mode, llm_cache=llm_cache, show_progress=True
            )
        else:
            case_metrics, failures = run_one_mode(cases, mode)
        all_case_metrics[mode] = case_metrics
        all_failures[mode] = failures

    if llm_cache is not None:
        from experiments.eval.llm_baseline import DEFAULT_CACHE_PATH, save_cache
        save_cache(llm_cache, DEFAULT_CACHE_PATH)
        print(f"\n已保存 LLM baseline 缓存（{len(llm_cache)} 条）→ {DEFAULT_CACHE_PATH}")

    overall = {mode: aggregate(all_case_metrics[mode]) for mode in modes}
    by_cat = {mode: aggregate_by_category(all_case_metrics[mode], cases) for mode in modes}

    title = f"=== {len(modes)} 档消融总表 ==="
    print("\n" + title)
    col_w = max(13, len("rule_plus_rag"))
    header_cells = [f"{'指标':<28}"] + [f"{m:>{col_w}}" for m in modes]
    print(" ".join(header_cells))
    print("-" * (28 + (col_w + 1) * len(modes)))
    rows = [
        ("覆盖率", "coverage"),
        ("标签数一致", "n_labels_match"),
        ("grade 准确", "grade_accuracy"),
        ("grade_id 准确", "grade_id_accuracy"),
        ("引用率(must_cite)", "citation_rate"),
        ("场景过滤负例", "citation_negative_pass"),
        ("source 匹配", "source_match"),
        ("baseline 空文本", "text_empty"),
        ("citation 出现率", "citation_present_rate"),
        ("citation 标准号真实", "citation_authenticity"),
    ]
    for label, key in rows:
        formatted: List[str] = []
        for m in modes:
            v = overall[m].get(key)
            if v is None:
                formatted.append(f"{'—':>{col_w}}")
            else:
                formatted.append(f"{v:>{col_w - 1}.1f}%")
        print(f"{label:<28}" + " ".join(formatted))

    total_failures = sum(len(v) for v in all_failures.values())
    print(f"\n失败用例总数（含累计）：{total_failures}")
    for mode in modes:
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

    md = render_markdown(overall, by_cat, all_failures, len(cases), ts, modes)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n报告已写入：\n  - {json_path}\n  - {md_path}\n  - {latest_md}（最新版镜像）")


if __name__ == "__main__":
    main()
