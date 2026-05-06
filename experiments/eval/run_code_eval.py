"""代码生成 + 沙箱执行 vs LLM 自由发挥直算 ：3 档消融评测

档位
----
- ``oracle``：直接读 ``expected.value``，作为评测器自校验天花板（不调 LLM）
- ``llm_direct``：LLM 看 query + data 直接给数值答案（不写代码）
- ``llm_with_code``：LLM 生成 ``compute(data)`` 代码 → 受限沙箱执行 → 取返回值

输出
----
- 控制台：3 档总表 + 按用例类别拆分 + 失败案例摘要
- ``experiments/results/code_eval_<时间戳>.{json,md}``：完整指标 + 每条用例输出
- ``experiments/results/code_eval_latest.md``：始终镜像最新版

缓存
----
- LLM 直算结果缓存到 ``experiments/results/code_baseline_cache.json``
- LLM 代码生成结果缓存到 ``experiments/results/code_gen_cache.json``
- 两层缓存独立，命中即跳过 LLM 调用，避免重复消耗 token
- ``--force-llm`` 强制重跑两层

防 hang 加固（与 llm_baseline / intent_eval 一致）
--------------------------------------------------
- 上游 ``ChatOpenAI`` 已带 ``timeout=60`` + ``max_retries=2``
- 主循环包在 try/finally 中，每条用例增量落盘缓存
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from src.analysis.code_generator import (
    CODE_GEN_PROMPT_VERSION,
    CodeGenResult,
    generate_code,
)
from src.config.settings import LLM_MODEL
from src.tools.code_executor import execute_code
from experiments.eval.code_baseline import (
    DEFAULT_CACHE_PATH as DIRECT_CACHE_PATH,
    load_cache as load_direct_cache,
    run_llm_direct,
    save_cache as save_direct_cache,
)
from experiments.eval.code_metrics import (
    aggregate,
    aggregate_by_category,
    evaluate_case,
    load_bench,
)


DEFAULT_BENCH = os.path.join("data", "test_cases", "code_exec_bench.jsonl")
DEFAULT_OUT = os.path.join("experiments", "results")
CODEGEN_CACHE_PATH = os.path.join(DEFAULT_OUT, "code_gen_cache.json")

DEFAULT_MODES: Tuple[str, ...] = ("oracle", "llm_direct", "llm_with_code")


# ---------------------------------------------------------------------------
# 代码生成缓存
# ---------------------------------------------------------------------------

def _make_codegen_cache_key(query: str, data: Any) -> str:
    payload = json.dumps(
        {"q": query, "d": data, "v": CODE_GEN_PROMPT_VERSION, "m": LLM_MODEL},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _load_codegen_cache() -> Dict[str, Any]:
    if not os.path.exists(CODEGEN_CACHE_PATH):
        return {}
    try:
        with open(CODEGEN_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_codegen_cache(cache: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CODEGEN_CACHE_PATH), exist_ok=True)
    with open(CODEGEN_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _save_safe(saver, *args) -> None:
    try:
        saver(*args)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 落盘失败：{exc}")


# ---------------------------------------------------------------------------
# 单档单条
# ---------------------------------------------------------------------------

def _run_oracle(case: Dict[str, Any]) -> Dict[str, Any]:
    """直接返回期望值，模拟评测器天花板。"""
    return {
        "value": case["expected"]["value"],
        "meta": {"reasoning": "oracle 直接读取 expected.value（评测器自校验）"},
    }


def _run_llm_direct(
    case: Dict[str, Any],
    cache: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """LLM 自由发挥直算。"""
    out = run_llm_direct(case["query"], case["data"], cache=cache)
    return {
        "value": out.get("value"),
        "meta": {
            "reasoning": out.get("reasoning"),
            "error": out.get("error"),
            "numeric_extra": out.get("numeric_extra"),
            "cache_hit": out.get("cache_hit"),
        },
    }


def _run_llm_with_code(
    case: Dict[str, Any],
    codegen_cache: Optional[Dict[str, Any]] = None,
    timeout: float = 5.0,
) -> Dict[str, Any]:
    """LLM 生成代码 + 受限沙箱执行。"""
    cache_key = _make_codegen_cache_key(case["query"], case["data"])
    cache_hit = False
    if codegen_cache is not None and cache_key in codegen_cache:
        cached = codegen_cache[cache_key]
        gen = CodeGenResult(
            code=cached.get("code", ""),
            reasoning=cached.get("reasoning"),
        )
        cache_hit = True
    else:
        gen = generate_code(case["query"], case["data"])
        if codegen_cache is not None:
            codegen_cache[cache_key] = {
                "code": gen.code,
                "reasoning": gen.reasoning,
            }

    code_generated = bool(gen.code and gen.code.strip())
    code_executable = False
    value: Any = None
    exec_error: Optional[str] = None

    if code_generated:
        result = execute_code(gen.code, case["data"], timeout=timeout)
        code_executable = result.success
        value = result.value
        exec_error = result.error
    else:
        exec_error = "代码生成失败（empty code）"

    return {
        "value": value,
        "meta": {
            "code_generated": code_generated,
            "code_executable": code_executable,
            "code": gen.code,
            "reasoning": gen.reasoning,
            "error": exec_error,
            "cache_hit": cache_hit,
        },
    }


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------

def run_one_mode(
    cases: List[Dict[str, Any]],
    mode: str,
    direct_cache: Optional[Dict[str, Any]] = None,
    codegen_cache: Optional[Dict[str, Any]] = None,
    show_progress: bool = True,
):
    n = len(cases)
    case_metrics: List[Dict[str, Any]] = []
    raw_outputs: List[Dict[str, Any]] = []

    for idx, case in enumerate(cases, 1):
        if mode == "oracle":
            out = _run_oracle(case)
            cache_hit = True
        elif mode == "llm_direct":
            out = _run_llm_direct(case, cache=direct_cache)
            cache_hit = bool(out["meta"].get("cache_hit"))
        elif mode == "llm_with_code":
            out = _run_llm_with_code(case, codegen_cache=codegen_cache)
            cache_hit = bool(out["meta"].get("cache_hit"))
        else:
            raise ValueError(f"未知 mode: {mode}")

        if show_progress:
            tag = "缓存" if cache_hit else "调用"
            print(f"  [{mode}] {idx:>2}/{n} {tag} {case['id']}", flush=True)

        if not cache_hit and mode == "llm_direct" and direct_cache is not None:
            _save_safe(save_direct_cache, direct_cache, DIRECT_CACHE_PATH)
        if not cache_hit and mode == "llm_with_code" and codegen_cache is not None:
            _save_safe(_save_codegen_cache, codegen_cache)

        m = evaluate_case(case, mode, out["value"], out["meta"])
        case_metrics.append(m)
        raw_outputs.append({
            "id": case["id"],
            "mode": mode,
            "value": out["value"],
            "meta": out["meta"],
        })

    return case_metrics, raw_outputs


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%"


def render_markdown(
    overall: Dict[str, Dict[str, Any]],
    by_cat: Dict[str, Dict[str, Dict[str, Any]]],
    all_case_metrics: Dict[str, List[Dict[str, Any]]],
    all_raw: Dict[str, List[Dict[str, Any]]],
    n_cases: int,
    ts: str,
    modes: Tuple[str, ...],
) -> str:
    lines: List[str] = []
    lines.append("# 代码生成 + 执行 vs LLM 自由直算 评测报告\n")
    lines.append(f"- 评测时间：{ts}")
    lines.append(f"- 用例总数：**{n_cases}**")
    lines.append(f"- 评测档位：{', '.join(modes)}")
    lines.append(f"- 模型：{LLM_MODEL}")
    lines.append("- 评测集：`data/test_cases/code_exec_bench.jsonl`")
    lines.append("- 评测脚本：`experiments/eval/run_code_eval.py`\n")

    lines.append("## 一、3 档消融总表\n")
    headers = ["指标"] + list(modes)
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] + [":---:"] * len(modes)) + "|")
    rows = [
        ("数值准确率（核心）", "numeric_accuracy"),
        ("代码生成率", "code_generated_rate"),
        ("代码可执行率", "code_executable_rate"),
    ]
    for label, key in rows:
        cells = [label]
        for m in modes:
            cells.append(_fmt_pct(overall[m].get(key)))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## 二、按用例类别拆分（数值准确率）\n")
    cats = sorted({c for m_dict in by_cat.values() for c in m_dict.keys()})
    headers = ["类别", "用例数"] + list(modes)
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] + [":---:"] * (len(headers) - 1)) + "|")
    for cat in cats:
        first_mode = modes[0]
        n = by_cat[first_mode].get(cat, {}).get("n_cases", 0)
        cells = [cat, str(n)]
        for m in modes:
            v = by_cat[m].get(cat, {}).get("numeric_accuracy")
            cells.append(_fmt_pct(v))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## 三、失败用例（仅展示 llm_direct / llm_with_code）\n")
    raw_by_mode_id: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for m in modes:
        raw_by_mode_id[m] = {r["id"]: r for r in all_raw.get(m, [])}

    for mode in modes:
        if mode == "oracle":
            continue
        failed = [m for m in all_case_metrics[mode] if not m.get("numeric_correct")]
        lines.append(f"### mode={mode}（{len(failed)} 条失败）\n")
        for fm in failed:
            cid = fm.get("id")
            raw = raw_by_mode_id[mode].get(cid, {})
            meta = raw.get("meta", {})
            lines.append(f"- **{cid}** [{fm.get('category')}]")
            lines.append(f"  - 期望：`{fm.get('expected_value')}`（type={fm.get('expected_type')}）")
            lines.append(f"  - 实际：`{fm.get('pred_value')}`")
            if mode == "llm_direct":
                if meta.get("reasoning"):
                    lines.append(f"  - reasoning: {meta['reasoning']}")
                if meta.get("error"):
                    lines.append(f"  - llm_error: {meta['error']}")
            elif mode == "llm_with_code":
                if not meta.get("code_generated"):
                    lines.append(f"  - 代码生成失败")
                elif not meta.get("code_executable"):
                    lines.append(f"  - 代码执行失败：{meta.get('error')}")
                else:
                    lines.append(f"  - 代码执行成功但结果错误（潜在算法 bug）")
                if meta.get("reasoning"):
                    lines.append(f"  - reasoning: {meta['reasoning']}")
                code = meta.get("code", "")
                if code:
                    lines.append("  - code:\n```python\n" + code + "\n```")
            lines.append("")
        if not failed:
            lines.append("  （本档无失败用例）\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="代码生成 + 执行 3 档消融评测")
    parser.add_argument("--bench", default=DEFAULT_BENCH)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument(
        "--force-llm", action="store_true", help="跳过两层缓存，强制重跑 LLM"
    )
    args = parser.parse_args()

    cases = load_bench(args.bench)
    print(f"加载 {len(cases)} 条评测用例（{args.bench}）")
    print(f"评测档位：{DEFAULT_MODES}")

    if args.force_llm:
        print("[--force-llm] 跳过两层缓存重跑")
        direct_cache: Dict[str, Any] = {}
        codegen_cache: Dict[str, Any] = {}
    else:
        direct_cache = load_direct_cache()
        codegen_cache = _load_codegen_cache()
        print(f"加载 LLM 直算缓存：{len(direct_cache)} 条")
        print(f"加载代码生成缓存：{len(codegen_cache)} 条")

    all_case_metrics: Dict[str, List[Dict[str, Any]]] = {}
    all_raw: Dict[str, List[Dict[str, Any]]] = {}

    try:
        for mode in DEFAULT_MODES:
            print(f"\n[mode={mode}] 开始")
            cm, raw = run_one_mode(
                cases, mode,
                direct_cache=direct_cache,
                codegen_cache=codegen_cache,
                show_progress=True,
            )
            all_case_metrics[mode] = cm
            all_raw[mode] = raw
    except KeyboardInterrupt:
        print("\n[interrupt] 用户中断，先落盘缓存…")
        _save_safe(save_direct_cache, direct_cache, DIRECT_CACHE_PATH)
        _save_safe(_save_codegen_cache, codegen_cache)
        raise
    finally:
        _save_safe(save_direct_cache, direct_cache, DIRECT_CACHE_PATH)
        _save_safe(_save_codegen_cache, codegen_cache)
        print(f"\n已保存 LLM 直算缓存（{len(direct_cache)} 条）→ {DIRECT_CACHE_PATH}")
        print(f"已保存代码生成缓存（{len(codegen_cache)} 条）→ {CODEGEN_CACHE_PATH}")

    overall = {m: aggregate(all_case_metrics[m]) for m in DEFAULT_MODES}
    by_cat = {m: aggregate_by_category(all_case_metrics[m]) for m in DEFAULT_MODES}

    print("\n=== 3 档消融总表 ===")
    col_w = 14
    header_cells = [f"{'指标':<22}"] + [f"{m:>{col_w}}" for m in DEFAULT_MODES]
    print(" ".join(header_cells))
    print("-" * (22 + (col_w + 1) * len(DEFAULT_MODES)))
    for label, key in [
        ("数值准确率（核心）", "numeric_accuracy"),
        ("代码生成率", "code_generated_rate"),
        ("代码可执行率", "code_executable_rate"),
    ]:
        cells = [f"{label:<22}"]
        for m in DEFAULT_MODES:
            v = overall[m].get(key)
            cells.append(f"{_fmt_pct(v):>{col_w}}")
        print(" ".join(cells))

    print("\n=== 按用例类别拆分（数值准确率） ===")
    cats = sorted({c for d in by_cat.values() for c in d.keys()})
    print(f"{'类别':<15}{'数':>4}  " + "  ".join(f"{m:>{col_w}}" for m in DEFAULT_MODES))
    print("-" * (15 + 6 + (col_w + 2) * len(DEFAULT_MODES)))
    for cat in cats:
        n = by_cat[DEFAULT_MODES[0]].get(cat, {}).get("n_cases", 0)
        cells = [f"{cat:<15}{n:>4}"]
        for m in DEFAULT_MODES:
            v = by_cat[m].get(cat, {}).get("numeric_accuracy")
            cells.append(f"{_fmt_pct(v):>{col_w}}")
        print("  ".join(cells))

    for mode in DEFAULT_MODES:
        failed = [m for m in all_case_metrics[mode] if not m.get("numeric_correct")]
        print(f"\n[{mode}] 失败用例：{len(failed)} / {len(cases)}")

    os.makedirs(args.out, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(args.out, f"code_eval_{ts}.json")
    md_path = os.path.join(args.out, f"code_eval_{ts}.md")
    latest_md = os.path.join(args.out, "code_eval_latest.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "n_cases": len(cases),
            "model": LLM_MODEL,
            "modes": list(DEFAULT_MODES),
            "overall": overall,
            "by_category": by_cat,
            "case_metrics": all_case_metrics,
            "raw_outputs": all_raw,
        }, f, ensure_ascii=False, indent=2)

    md = render_markdown(
        overall, by_cat, all_case_metrics, all_raw, len(cases), ts, DEFAULT_MODES
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n报告已写入：\n  - {json_path}\n  - {md_path}\n  - {latest_md}（最新版镜像）")


if __name__ == "__main__":
    main()
