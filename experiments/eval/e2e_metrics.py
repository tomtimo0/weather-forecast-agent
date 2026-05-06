"""端到端评测指标：关键事实点匹配 + 引用/分级/建议检测 + LLM-as-judge

设计原则
--------
真实 API 数据每次调用都不同（动态变化），无法用具体数值断言。指标体系
聚焦于"**结构性证据**"——回答是否覆盖了用户期望的事实点、是否引用了权威
标准、是否给出了规范的分级、是否提供了明确的决策建议。

5 类断言
--------
1. **key_facts**：用例自带的"关键事实点"列表，每项类型：
   - ``regex``：正则匹配（如温度数值 ``\\d+\\s*°?[CcF]``）
   - ``keyword_all``：全部关键词必须命中
   - ``keyword_any``：任一关键词命中即可
   - ``topic_coverage``：从词表中至少命中 ``min_match`` 个

2. **citation_present**：回答是否包含权威标准号（GB/T xxx-yyyy 等）
3. **grading_present**：回答是否使用了气象规范分级词（小雨/中雨/大雨/暴雨
   /微风/和风/3级风/严寒/酷热/雾/大雾 等）
4. **advice_present**：回答是否给出了明确决策建议（适合/不适合/建议/推荐 等）
5. **judge_score**：LLM-as-judge 4 维度打分（事实性 / 完整性 / 专业性 / 流畅性，
   每项 0-5），由独立的 judge LLM 不看金标准、仅看 query+answer 给分

综合通过判定
------------
``case_pass`` = ``key_facts_recall >= 0.8`` AND
                ``judge_overall >= 3.0`` AND
                （如 expected_should_cite_standard 则 citation_present 必须 True）AND
                （如 expected_should_have_grading 则 grading_present 必须 True）AND
                （如 expected_should_have_advice 则 advice_present 必须 True）

聚合指标
--------
- ``e2e_pass_rate``：综合通过率（端到端任务完成率，论文核心指标）
- ``key_fact_recall_avg``：关键事实点平均命中率
- ``citation_rate`` / ``grading_rate`` / ``advice_rate``：三类条件性指标
- ``judge_score_avg``：4 维度 judge 打分均值
- ``tool_calls_avg``：平均工具调用次数
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


# ---------------------------------------------------------------------------
# 词表
# ---------------------------------------------------------------------------

# GB/T xxx-yyyy 与同等级国家/行业标准号
_CITATION_PATTERNS = [
    r"GB[\s/]*T\s*\d{2,5}(?:[\.\-]\d+)?(?:-\d{4})?",
    r"GB\s*\d{2,5}(?:[\.\-]\d+)?(?:-\d{4})?",
    r"WMO\s*[A-Za-z\-\d]+",
    r"QX[\s/]*T?\s*\d{2,5}(?:-\d{4})?",
    r"HJ\s*\d{2,5}(?:-\d{4})?",
]

# 气象分级词（覆盖降水/风力/温度/湿度/能见度/紫外线/空气质量等）
_GRADING_KEYWORDS = [
    # 降水分级
    "小雨", "中雨", "大雨", "暴雨", "大暴雨", "特大暴雨", "毛毛雨", "阵雨",
    "小雪", "中雪", "大雪", "暴雪", "雨夹雪",
    # 蒲福风级
    "无风", "软风", "轻风", "微风", "和风", "清风", "强风", "疾风", "大风",
    "烈风", "狂风", "暴风", "飓风",
    # 温度分级
    "严寒", "寒冷", "凉爽", "凉", "舒适", "温暖", "炎热", "酷热", "高温",
    # 湿度分级
    "干燥", "适宜", "潮湿",
    # 能见度
    "雾", "轻雾", "大雾", "浓雾", "强浓雾", "特强浓雾",
    # 紫外线
    "弱", "中等", "强", "很强", "极强",
    # 空气质量
    "优", "良", "轻度污染", "中度污染", "重度污染", "严重污染",
]

# 风力级别匹配（"3级"、"7级风"、"大风蓝色预警"等）
_WIND_LEVEL_PATTERN = re.compile(r"\d{1,2}\s*[-至到~]\s*\d{1,2}\s*级|\d{1,2}\s*级(?:风)?")
_TEMP_GRADING_PATTERN = re.compile(r"≥\s*35|高于\s*35|超过\s*35|≤\s*-?\d+")

# 决策建议词
_ADVICE_KEYWORDS = [
    "适合", "不适合", "建议", "推荐", "不推荐", "可以", "不可以", "应",
    "不应", "需要", "不需要", "避免", "谨慎", "注意", "宜", "不宜",
    "稳妥", "可考虑", "请", "务必",
]


# ---------------------------------------------------------------------------
# 评测集加载
# ---------------------------------------------------------------------------

def load_bench(path: str) -> List[Dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# 关键事实点匹配
# ---------------------------------------------------------------------------

def _match_one_fact(answer: str, fact: Dict[str, Any]) -> bool:
    if not isinstance(answer, str) or not answer:
        return False
    ftype = fact.get("type", "")
    if ftype == "regex":
        pattern = fact.get("pattern", "")
        if not pattern:
            return False
        try:
            return bool(re.search(pattern, answer))
        except re.error:
            return False
    if ftype == "keyword_all":
        values = fact.get("values", [])
        return all(v in answer for v in values)
    if ftype == "keyword_any":
        values = fact.get("values", [])
        return any(v in answer for v in values)
    if ftype == "topic_coverage":
        values = fact.get("values", [])
        min_match = int(fact.get("min_match", 1))
        hit = sum(1 for v in values if v in answer)
        return hit >= min_match
    return False


def match_key_facts(answer: str, facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not facts:
        return {"hits": [], "n_total": 0, "n_hit": 0, "recall": 1.0}
    hits = []
    for f in facts:
        ok = _match_one_fact(answer, f)
        hits.append({"name": f.get("name", ""), "type": f.get("type", ""), "hit": ok})
    n_hit = sum(1 for h in hits if h["hit"])
    return {
        "hits": hits,
        "n_total": len(facts),
        "n_hit": n_hit,
        "recall": n_hit / len(facts),
    }


# ---------------------------------------------------------------------------
# 引用 / 分级 / 建议 检测
# ---------------------------------------------------------------------------

def detect_citation(answer: str) -> bool:
    if not isinstance(answer, str):
        return False
    for pat in _CITATION_PATTERNS:
        if re.search(pat, answer, flags=re.IGNORECASE):
            return True
    return False


def detect_grading(answer: str) -> bool:
    if not isinstance(answer, str):
        return False
    for kw in _GRADING_KEYWORDS:
        if kw in answer:
            return True
    if _WIND_LEVEL_PATTERN.search(answer):
        return True
    if _TEMP_GRADING_PATTERN.search(answer):
        return True
    return False


def detect_advice(answer: str) -> bool:
    if not isinstance(answer, str):
        return False
    return any(kw in answer for kw in _ADVICE_KEYWORDS)


# ---------------------------------------------------------------------------
# LLM-as-judge
# ---------------------------------------------------------------------------

JUDGE_PROMPT_VERSION = "v1"


JUDGE_SYSTEM_PROMPT = """你是一个严格的气象问答质量评审员。
你只看到用户的查询和系统的回答，请客观打分。**不要试图猜测金标准答案**，
只评判回答本身的质量。

## 4 维度打分（每项 0-5 分，整数）

1. **factuality（事实性）**：回答提供的具体数值、日期、地点、城市名是否
   自洽、合理、无明显矛盾；如有"明显错误的事实"（如"昨天明天将……"
   /逻辑混乱/数值离谱）应扣分。
2. **completeness（完整性）**：回答是否覆盖了用户问题的核心要素；如用户
   问"明天会下雨吗"，至少应给出降水状况；如用户问"穿什么衣服"，至少应
   给出温度与穿衣建议。
3. **expertise（专业性）**：回答是否用了规范的气象分级词（小雨/暴雨/
   3级风/雾/严寒/酷热等）+ 是否引用了权威标准号（GB/T xxx）+ 是否避免
   了凭空捏造的阈值。仅有数值无解读 → 2-3 分；有规范分级 → 4 分；
   有规范分级 + 标准引用 → 5 分。
4. **fluency（流畅性）**：回答是否表达清晰、结构清楚、读起来顺畅；
   有"工具返回错误"等无意义内容应扣分。

## 输出
请输出结构化对象，包含 4 个 0-5 整数分 + 一句简短总评。"""


class JudgeResult(BaseModel):
    factuality: int = Field(ge=0, le=5, description="事实性 0-5")
    completeness: int = Field(ge=0, le=5, description="完整性 0-5")
    expertise: int = Field(ge=0, le=5, description="专业性 0-5")
    fluency: int = Field(ge=0, le=5, description="流畅性 0-5")
    overall_comment: Optional[str] = Field(
        default=None, description="一句简短总评，便于人工复盘"
    )


_judge_singleton = None


def _get_judge_llm():
    global _judge_singleton
    if _judge_singleton is None:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=0,
            timeout=60,
            max_retries=2,
        )
        _judge_singleton = llm.with_structured_output(
            JudgeResult, method="function_calling"
        )
    return _judge_singleton


def make_judge_cache_key(query: str, answer: str, model: str = LLM_MODEL) -> str:
    payload = json.dumps(
        {"q": query, "a": answer, "v": JUDGE_PROMPT_VERSION, "m": model},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def run_judge(
    query: str,
    answer: str,
    cache: Optional[Dict[str, Any]] = None,
    max_retries: int = 1,
) -> Dict[str, Any]:
    """对单条 (query, answer) 调 LLM-as-judge 打 4 维度分。

    Returns:
        ``{"factuality", "completeness", "expertise", "fluency", "overall",
           "comment", "cache_hit"}``
    """
    if not answer or not isinstance(answer, str):
        return {
            "factuality": 0,
            "completeness": 0,
            "expertise": 0,
            "fluency": 0,
            "overall": 0.0,
            "comment": "回答为空",
            "cache_hit": False,
            "error": "empty_answer",
        }

    cache_key = make_judge_cache_key(query, answer)
    if cache is not None and cache_key in cache:
        cached = cache[cache_key]
        return {**cached, "cache_hit": True}

    structured = _get_judge_llm()
    user_msg = (
        f"## 用户查询\n{query}\n\n"
        f"## 系统回答\n{answer}\n\n"
        f"请给出 4 维度打分。"
    )
    last_error = ""
    judge: Optional[JudgeResult] = None
    for _attempt in range(max_retries + 1):
        try:
            raw = structured.invoke([
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ])
            if isinstance(raw, JudgeResult):
                judge = raw
                break
            last_error = "judge 未触发结构化输出"
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"

    if judge is None:
        return {
            "factuality": 0, "completeness": 0, "expertise": 0, "fluency": 0,
            "overall": 0.0,
            "comment": f"judge 失败：{last_error}",
            "cache_hit": False,
            "error": last_error,
        }

    overall = (judge.factuality + judge.completeness + judge.expertise + judge.fluency) / 4.0
    out = {
        "factuality": judge.factuality,
        "completeness": judge.completeness,
        "expertise": judge.expertise,
        "fluency": judge.fluency,
        "overall": round(overall, 3),
        "comment": judge.overall_comment,
        "cache_hit": False,
    }
    if cache is not None:
        cache[cache_key] = {k: v for k, v in out.items() if k != "cache_hit"}
    return out


# ---------------------------------------------------------------------------
# 单条聚合
# ---------------------------------------------------------------------------

def evaluate_case(
    case: Dict[str, Any],
    mode: str,
    answer: str,
    tool_calls: List[Dict[str, Any]],
    judge_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    expected = case.get("expected", {})
    facts = expected.get("key_facts", [])

    fact_match = match_key_facts(answer, facts)
    citation = detect_citation(answer)
    grading = detect_grading(answer)
    advice = detect_advice(answer)

    pass_facts = fact_match["recall"] >= 0.8
    pass_citation = (not expected.get("should_cite_standard")) or citation
    pass_grading = (not expected.get("should_have_grading")) or grading
    pass_advice = (not expected.get("should_have_advice")) or advice

    judge_overall = (judge_result or {}).get("overall", 0.0)
    pass_judge = judge_overall >= 3.0

    case_pass = pass_facts and pass_citation and pass_grading and pass_advice and pass_judge

    return {
        "id": case["id"],
        "category": case.get("category"),
        "mode": mode,
        "answer_len": len(answer or ""),
        "tool_calls_count": len(tool_calls),
        "key_fact_recall": fact_match["recall"],
        "key_fact_n_hit": fact_match["n_hit"],
        "key_fact_n_total": fact_match["n_total"],
        "key_fact_hits": fact_match["hits"],
        "citation_present": citation,
        "grading_present": grading,
        "advice_present": advice,
        "expected_should_cite": bool(expected.get("should_cite_standard")),
        "expected_should_grade": bool(expected.get("should_have_grading")),
        "expected_should_advise": bool(expected.get("should_have_advice")),
        "judge": judge_result or {},
        "pass_facts": pass_facts,
        "pass_citation": pass_citation,
        "pass_grading": pass_grading,
        "pass_advice": pass_advice,
        "pass_judge": pass_judge,
        "case_pass": case_pass,
    }


# ---------------------------------------------------------------------------
# 聚合
# ---------------------------------------------------------------------------

def _avg(values: Iterable[float]) -> Optional[float]:
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _avg_bool(values: Iterable[bool]) -> Optional[float]:
    values = [bool(v) for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def aggregate(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not metrics:
        return {"n_cases": 0}
    return {
        "n_cases": len(metrics),
        "e2e_pass_rate": _avg_bool(m["case_pass"] for m in metrics),
        "key_fact_recall_avg": _avg(m["key_fact_recall"] for m in metrics),
        "citation_rate": _avg_bool(m["citation_present"] for m in metrics),
        "grading_rate": _avg_bool(m["grading_present"] for m in metrics),
        "advice_rate": _avg_bool(m["advice_present"] for m in metrics),
        "judge_factuality_avg": _avg(m["judge"].get("factuality", 0) for m in metrics),
        "judge_completeness_avg": _avg(m["judge"].get("completeness", 0) for m in metrics),
        "judge_expertise_avg": _avg(m["judge"].get("expertise", 0) for m in metrics),
        "judge_fluency_avg": _avg(m["judge"].get("fluency", 0) for m in metrics),
        "judge_overall_avg": _avg(m["judge"].get("overall", 0) for m in metrics),
        "tool_calls_avg": _avg(m["tool_calls_count"] for m in metrics),
    }


def aggregate_by_category(metrics: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in metrics:
        bucket[m.get("category") or "uncategorized"].append(m)
    return {cat: aggregate(items) for cat, items in bucket.items()}


__all__ = [
    "load_bench",
    "match_key_facts",
    "detect_citation",
    "detect_grading",
    "detect_advice",
    "run_judge",
    "evaluate_case",
    "aggregate",
    "aggregate_by_category",
    "make_judge_cache_key",
]
