"""端到端任务完成率评测：full_agent vs ablated_agent 双档对照

档位
----
- ``full``：完整 react_agent（含 search_knowledge + bridge_weather_data 双通路 RAG 工具）
- ``ablated``：去掉双通路 RAG 工具的对照 agent（仅 9 个气象 API 工具）

两档共享同一份意图识别 + 参数补全前置（保证输入侧公平），只在「拿到原始
API 数据后如何解读」上不同。

输出
----
- 控制台：双档总表 + 按场景类别拆分 + 失败用例摘要
- ``experiments/results/e2e_eval_<时间戳>.{json,md}``：完整指标 + 每条用例
- ``experiments/results/e2e_eval_latest.md``：始终镜像最新版

缓存
----
- ``experiments/results/e2e_agent_cache.json``：(query, mode, model) → agent 输出
- ``experiments/results/e2e_judge_cache.json``：(query, answer, model) → judge 4 维度分

防 hang 加固
------------
- ``ChatOpenAI`` 已带 ``timeout=90`` + ``max_retries=2``
- agent 单次 stream 设 ``max_iters=12`` 防 react 循环失控
- 主循环包在 ``try/finally`` 中，每条用例增量落盘两层缓存
- 意图识别 / 补全统一前置一次，缓存 ``WeatherIntent`` 与 ``CompletionResult``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from src.config.settings import LLM_MODEL
from src.intent.completer import complete_intent
from src.intent.recognizer import recognize_intent
from src.intent.schema import CompletionResult, WeatherIntent
from experiments.eval.e2e_agent_runner import run_one_query
from experiments.eval.e2e_metrics import (
    aggregate,
    aggregate_by_category,
    evaluate_case,
    load_bench,
    make_judge_cache_key,
    run_judge,
)


DEFAULT_BENCH = os.path.join("data", "test_cases", "e2e_bench.jsonl")
DEFAULT_OUT = os.path.join("experiments", "results")
AGENT_CACHE_PATH = os.path.join(DEFAULT_OUT, "e2e_agent_cache.json")
JUDGE_CACHE_PATH = os.path.join(DEFAULT_OUT, "e2e_judge_cache.json")
INTENT_CACHE_PATH = os.path.join(DEFAULT_OUT, "e2e_intent_cache.json")

DEFAULT_MODES: Tuple[str, ...] = ("ablated", "full")


# ---------------------------------------------------------------------------
# 缓存：agent 输出 / judge 输出 / 前置意图
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json_safe(data: Dict[str, Any], path: str) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] 落盘失败 {path}: {exc}")


def _make_agent_cache_key(query: str, mode: str) -> str:
    payload = json.dumps(
        {"q": query, "m": mode, "model": LLM_MODEL, "v": "v1"},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _make_intent_cache_key(query: str) -> str:
    payload = json.dumps(
        {"q": query, "model": LLM_MODEL, "v": "v1"},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 前置：意图识别 + 补全（缓存）
# ---------------------------------------------------------------------------

def _prefetch_completion(
    query: str,
    intent_cache: Dict[str, Any],
) -> Tuple[CompletionResult, bool]:
    """对单条 query 跑意图识别 + 补全，缓存命中直接返回。

    Returns:
        (completion, cache_hit)
    """
    cache_key = _make_intent_cache_key(query)
    if cache_key in intent_cache:
        cached = intent_cache[cache_key]
        try:
            intent = WeatherIntent.model_validate(cached["intent"])
            completion = CompletionResult.model_validate(cached["completion"])
            return completion, True
        except Exception:
            pass

    intent = recognize_intent(query)
    completion = complete_intent(intent, conversation_context=None)
    intent_cache[cache_key] = {
        "intent": intent.model_dump(),
        "completion": completion.model_dump(),
    }
    return completion, False


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------

def run_one_mode(
    cases: List[Dict[str, Any]],
    mode: str,
    intent_cache: Dict[str, Any],
    agent_cache: Dict[str, Any],
    judge_cache: Dict[str, Any],
    show_progress: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    n = len(cases)
    case_metrics: List[Dict[str, Any]] = []
    raw_outputs: List[Dict[str, Any]] = []

    for idx, case in enumerate(cases, 1):
        query = case["query"]

        # 1. 前置意图识别
        completion, intent_hit = _prefetch_completion(query, intent_cache)
        if not intent_hit:
            _save_json_safe(intent_cache, INTENT_CACHE_PATH)

        # 2. 跑 agent（按 mode 缓存）
        agent_key = _make_agent_cache_key(query, mode)
        agent_hit = agent_key in agent_cache
        if agent_hit:
            agent_out = agent_cache[agent_key]
        else:
            agent_out = run_one_query(mode=mode, query=query, completion=completion)
            agent_cache[agent_key] = {
                "answer": agent_out.get("answer", ""),
                "tool_calls": agent_out.get("tool_calls", []),
                "elapsed_ms": agent_out.get("elapsed_ms"),
                "iter_count": agent_out.get("iter_count"),
                "error": agent_out.get("error"),
            }
            _save_json_safe(agent_cache, AGENT_CACHE_PATH)

        if show_progress:
            tag = "缓存" if agent_hit else "调用"
            err = agent_out.get("error")
            err_tag = f" ⚠ {err}" if err else ""
            n_calls = len(agent_out.get("tool_calls", []))
            print(
                f"  [{mode}] {idx:>2}/{n} {tag} {case['id']:<32}  "
                f"answer_len={len(agent_out.get('answer','')):>4}  "
                f"tool_calls={n_calls:>2}{err_tag}",
                flush=True,
            )

        # 3. judge 打分（缓存）
        answer = agent_out.get("answer", "")
        judge_key = make_judge_cache_key(query, answer)
        judge_hit = judge_key in judge_cache
        if judge_hit:
            judge_result = {**judge_cache[judge_key], "cache_hit": True}
        else:
            judge_result = run_judge(query, answer, cache=judge_cache)
            _save_json_safe(judge_cache, JUDGE_CACHE_PATH)

        # 4. 计算指标
        m = evaluate_case(
            case=case,
            mode=mode,
            answer=answer,
            tool_calls=agent_out.get("tool_calls", []),
            judge_result=judge_result,
        )
        case_metrics.append(m)
        raw_outputs.append({
            "id": case["id"],
            "mode": mode,
            "query": query,
            "answer": answer,
            "tool_calls": agent_out.get("tool_calls", []),
            "elapsed_ms": agent_out.get("elapsed_ms"),
            "iter_count": agent_out.get("iter_count"),
            "error": agent_out.get("error"),
            "judge": judge_result,
        })

    return case_metrics, raw_outputs


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return f"{v * 100:.1f}%"


def _fmt_num(v: Optional[float], digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}"


def render_markdown(
    overall: Dict[str, Dict[str, Any]],
    by_cat: Dict[str, Dict[str, Dict[str, Any]]],
    all_metrics: Dict[str, List[Dict[str, Any]]],
    all_raw: Dict[str, List[Dict[str, Any]]],
    n_cases: int,
    ts: str,
    modes: Tuple[str, ...],
) -> str:
    L: List[str] = []
    L.append("# 端到端任务完成率评测报告（A1）\n")
    L.append(f"- 评测时间：{ts}")
    L.append(f"- 用例总数：**{n_cases}**")
    L.append(f"- 评测档位：{', '.join(modes)}")
    L.append(f"- 模型：{LLM_MODEL}")
    L.append("- 评测集：`data/test_cases/e2e_bench.jsonl`")
    L.append("- 评测脚本：`experiments/eval/run_e2e_eval.py`\n")

    L.append("## 一、双档总表\n")
    headers = ["指标"] + list(modes)
    L.append("| " + " | ".join(headers) + " |")
    L.append("|" + "|".join(["---"] + [":---:"] * len(modes)) + "|")
    rows = [
        ("**端到端通过率（核心）**", "e2e_pass_rate", "pct"),
        ("关键事实点平均命中率", "key_fact_recall_avg", "pct"),
        ("权威标准引用率", "citation_rate", "pct"),
        ("规范分级出现率", "grading_rate", "pct"),
        ("决策建议出现率", "advice_rate", "pct"),
        ("Judge 事实性（0-5）", "judge_factuality_avg", "num"),
        ("Judge 完整性（0-5）", "judge_completeness_avg", "num"),
        ("Judge 专业性（0-5）", "judge_expertise_avg", "num"),
        ("Judge 流畅性（0-5）", "judge_fluency_avg", "num"),
        ("**Judge 综合（0-5）**", "judge_overall_avg", "num"),
        ("平均工具调用次数", "tool_calls_avg", "num"),
    ]
    for label, key, kind in rows:
        cells = [label]
        for m in modes:
            v = overall[m].get(key)
            cells.append(_fmt_pct(v) if kind == "pct" else _fmt_num(v))
        L.append("| " + " | ".join(cells) + " |")
    L.append("")

    L.append("## 二、按场景类别拆分（端到端通过率）\n")
    cats = sorted({c for d in by_cat.values() for c in d.keys()})
    headers = ["类别", "用例数"] + list(modes)
    L.append("| " + " | ".join(headers) + " |")
    L.append("|" + "|".join(["---"] + [":---:"] * (len(headers) - 1)) + "|")
    for cat in cats:
        first = modes[0]
        n = by_cat[first].get(cat, {}).get("n_cases", 0)
        cells = [cat, str(n)]
        for m in modes:
            v = by_cat[m].get(cat, {}).get("e2e_pass_rate")
            cells.append(_fmt_pct(v))
        L.append("| " + " | ".join(cells) + " |")
    L.append("")

    L.append("## 三、按场景类别拆分（Judge 综合分 / 引用率 / 分级率）\n")
    for label, key, kind in [
        ("Judge 综合（0-5）", "judge_overall_avg", "num"),
        ("权威标准引用率", "citation_rate", "pct"),
        ("规范分级出现率", "grading_rate", "pct"),
    ]:
        L.append(f"### {label}\n")
        headers = ["类别", "用例数"] + list(modes)
        L.append("| " + " | ".join(headers) + " |")
        L.append("|" + "|".join(["---"] + [":---:"] * (len(headers) - 1)) + "|")
        for cat in cats:
            first = modes[0]
            n = by_cat[first].get(cat, {}).get("n_cases", 0)
            cells = [cat, str(n)]
            for m in modes:
                v = by_cat[m].get(cat, {}).get(key)
                cells.append(_fmt_pct(v) if kind == "pct" else _fmt_num(v))
            L.append("| " + " | ".join(cells) + " |")
        L.append("")

    L.append("## 四、失败用例摘要\n")
    for mode in modes:
        failed = [m for m in all_metrics[mode] if not m.get("case_pass")]
        L.append(f"### mode={mode}（{len(failed)} 条失败 / {n_cases}）\n")
        raw_by_id = {r["id"]: r for r in all_raw.get(mode, [])}
        for fm in failed:
            cid = fm.get("id")
            raw = raw_by_id.get(cid, {})
            reasons = []
            if not fm.get("pass_facts"):
                reasons.append(
                    f"事实点 recall={fm.get('key_fact_recall'):.2f} "
                    f"({fm.get('key_fact_n_hit')}/{fm.get('key_fact_n_total')})"
                )
            if not fm.get("pass_citation"):
                reasons.append("缺权威引用")
            if not fm.get("pass_grading"):
                reasons.append("缺规范分级")
            if not fm.get("pass_advice"):
                reasons.append("缺决策建议")
            if not fm.get("pass_judge"):
                reasons.append(
                    f"Judge 综合={fm.get('judge', {}).get('overall', 0):.2f} < 3"
                )
            L.append(f"- **{cid}** [{fm.get('category')}] —— {'; '.join(reasons)}")
            ans = raw.get("answer", "")
            if ans:
                snippet = ans.replace("\n", " ").strip()
                if len(snippet) > 220:
                    snippet = snippet[:220] + "…"
                L.append(f"  - answer: {snippet}")
            jc = (raw.get("judge") or {}).get("comment")
            if jc:
                L.append(f"  - judge: {jc}")
            L.append("")
        if not failed:
            L.append("  （本档无失败用例）\n")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="端到端任务完成率评测（A1）")
    parser.add_argument("--bench", default=DEFAULT_BENCH)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument(
        "--force-llm",
        action="store_true",
        help="跳过三层缓存，强制重跑 agent + judge",
    )
    parser.add_argument(
        "--only-mode",
        default=None,
        choices=["full", "ablated"],
        help="仅跑指定档（调试用）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="仅跑前 N 条用例（debug/smoke test，0 = 全部）",
    )
    args = parser.parse_args()

    cases = load_bench(args.bench)
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]
        print(f"[--limit {args.limit}] 仅评测前 {len(cases)} 条")
    print(f"加载 {len(cases)} 条端到端用例（{args.bench}）")

    if args.only_mode:
        modes: Tuple[str, ...] = (args.only_mode,)
    else:
        modes = DEFAULT_MODES
    print(f"评测档位：{modes}")

    if args.force_llm:
        print("[--force-llm] 跳过三层缓存重跑")
        intent_cache: Dict[str, Any] = {}
        agent_cache: Dict[str, Any] = {}
        judge_cache: Dict[str, Any] = {}
    else:
        intent_cache = _load_json(INTENT_CACHE_PATH)
        agent_cache = _load_json(AGENT_CACHE_PATH)
        judge_cache = _load_json(JUDGE_CACHE_PATH)
        print(
            f"加载缓存 → intent: {len(intent_cache)} 条 / "
            f"agent: {len(agent_cache)} 条 / judge: {len(judge_cache)} 条"
        )

    all_metrics: Dict[str, List[Dict[str, Any]]] = {}
    all_raw: Dict[str, List[Dict[str, Any]]] = {}

    try:
        for mode in modes:
            print(f"\n[mode={mode}] 开始")
            cm, raw = run_one_mode(
                cases, mode,
                intent_cache=intent_cache,
                agent_cache=agent_cache,
                judge_cache=judge_cache,
                show_progress=True,
            )
            all_metrics[mode] = cm
            all_raw[mode] = raw
    except KeyboardInterrupt:
        print("\n[interrupt] 用户中断，先落盘缓存…")
        _save_json_safe(intent_cache, INTENT_CACHE_PATH)
        _save_json_safe(agent_cache, AGENT_CACHE_PATH)
        _save_json_safe(judge_cache, JUDGE_CACHE_PATH)
        raise
    finally:
        _save_json_safe(intent_cache, INTENT_CACHE_PATH)
        _save_json_safe(agent_cache, AGENT_CACHE_PATH)
        _save_json_safe(judge_cache, JUDGE_CACHE_PATH)
        print(
            f"\n已保存缓存 → intent: {len(intent_cache)} / "
            f"agent: {len(agent_cache)} / judge: {len(judge_cache)}"
        )

    overall = {m: aggregate(all_metrics[m]) for m in modes}
    by_cat = {m: aggregate_by_category(all_metrics[m]) for m in modes}

    print("\n=== 双档总表 ===")
    col_w = 14
    header = [f"{'指标':<24}"] + [f"{m:>{col_w}}" for m in modes]
    print(" ".join(header))
    print("-" * (24 + (col_w + 1) * len(modes)))
    rows = [
        ("端到端通过率（核心）", "e2e_pass_rate", "pct"),
        ("关键事实点 recall", "key_fact_recall_avg", "pct"),
        ("权威标准引用率", "citation_rate", "pct"),
        ("规范分级出现率", "grading_rate", "pct"),
        ("决策建议出现率", "advice_rate", "pct"),
        ("Judge 事实性", "judge_factuality_avg", "num"),
        ("Judge 完整性", "judge_completeness_avg", "num"),
        ("Judge 专业性", "judge_expertise_avg", "num"),
        ("Judge 流畅性", "judge_fluency_avg", "num"),
        ("Judge 综合（0-5）", "judge_overall_avg", "num"),
        ("平均工具调用数", "tool_calls_avg", "num"),
    ]
    for label, key, kind in rows:
        cells = [f"{label:<24}"]
        for m in modes:
            v = overall[m].get(key)
            txt = _fmt_pct(v) if kind == "pct" else _fmt_num(v)
            cells.append(f"{txt:>{col_w}}")
        print(" ".join(cells))

    print("\n=== 按类别拆分（端到端通过率） ===")
    cats = sorted({c for d in by_cat.values() for c in d.keys()})
    print(f"{'类别':<18}{'数':>4}  " + "  ".join(f"{m:>{col_w}}" for m in modes))
    print("-" * (18 + 6 + (col_w + 2) * len(modes)))
    for cat in cats:
        first = modes[0]
        n = by_cat[first].get(cat, {}).get("n_cases", 0)
        cells = [f"{cat:<18}{n:>4}"]
        for m in modes:
            v = by_cat[m].get(cat, {}).get("e2e_pass_rate")
            cells.append(f"{_fmt_pct(v):>{col_w}}")
        print("  ".join(cells))

    for mode in modes:
        n_pass = sum(1 for m in all_metrics[mode] if m.get("case_pass"))
        print(f"\n[{mode}] 通过 / 总数 = {n_pass} / {len(all_metrics[mode])}")

    os.makedirs(args.out, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(args.out, f"e2e_eval_{ts}.json")
    md_path = os.path.join(args.out, f"e2e_eval_{ts}.md")
    latest_md = os.path.join(args.out, "e2e_eval_latest.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "n_cases": len(cases),
            "model": LLM_MODEL,
            "modes": list(modes),
            "overall": overall,
            "by_category": by_cat,
            "case_metrics": all_metrics,
            "raw_outputs": all_raw,
        }, f, ensure_ascii=False, indent=2)

    md = render_markdown(overall, by_cat, all_metrics, all_raw, len(cases), ts, modes)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"\n报告已写入：\n  - {json_path}\n  - {md_path}\n  - {latest_md}（镜像）")


if __name__ == "__main__":
    main()
