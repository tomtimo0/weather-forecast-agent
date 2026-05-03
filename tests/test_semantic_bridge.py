"""语义桥接最小可行版本测试

覆盖三种核心场景：
1. 数值分级正确性（纯规则，不依赖 LLM 与 RAG）
2. RAG 富化能拿到权威条款（需知识库已索引）
3. 三种 mode 的输出差异，对应论文消融实验
"""

from src.analysis.classifiers.precipitation import classify_precipitation
from src.analysis.semantic_bridge import bridge_weather_dict


# ---------------------------------------------------------------- 1. 分级测试
PRECIP_24H_CASES = [
    # (输入mm, 期望等级, 期望grade_id前缀)
    (0.0,    "无降水或微量",  None),
    (5.0,    "小雨",         "grading_precip_24h_light"),
    (15.0,   "中雨",         "grading_precip_24h_moderate"),
    (35.0,   "大雨",         "grading_precip_24h_heavy"),
    (80.0,   "暴雨",         "grading_precip_24h_rainstorm"),
    (150.0,  "大暴雨",       "grading_precip_24h_heavy_rainstorm"),
    (300.0,  "特大暴雨",     "grading_precip_24h_extreme_rainstorm"),
]


def test_precipitation_grading():
    print("=" * 70)
    print("【测试 1】降水分级正确性")
    print("=" * 70)
    pass_count = 0
    for value, expected_grade, expected_id in PRECIP_24H_CASES:
        label = classify_precipitation(value, "24h")
        ok = label.grade == expected_grade and label.grade_id == expected_id
        if ok:
            pass_count += 1
        status = "PASS" if ok else "FAIL"
        print(f"  {value:>6}mm/24h → grade={label.grade}, id={label.grade_id}  [{status}]")
    print(f"\n通过 {pass_count}/{len(PRECIP_24H_CASES)}\n")


# ---------------------------------------------------------------- 2. RAG 富化
def test_rag_enrichment():
    print("=" * 70)
    print("【测试 2】RAG 富化能否拿到权威 impact 与 citation")
    print("=" * 70)
    result = bridge_weather_dict({"precip_24h": 35.0}, scene="出行", mode="rule_plus_rag")
    label = result["labels"][0]
    has_impact = bool(label.impact)
    has_citation = bool(label.citation)
    is_rag = label.source == "rule_plus_rag"
    print(f"  grade        = {label.grade}")
    print(f"  impact       = {label.impact!r}")
    print(f"  citation     = {label.citation!r}")
    print(f"  source       = {label.source}")
    status = "PASS" if (has_impact and has_citation and is_rag) else "FAIL"
    print(f"\n[{status}] impact/citation/source 三项{'齐全' if status == 'PASS' else '缺失'}\n")


# ---------------------------------------------------------------- 3. 三种 mode 对比
def test_three_modes():
    print("=" * 70)
    print("【测试 3】三种 mode 输出对比（消融实验依据）")
    print("=" * 70)
    sample = {"precip_24h": 35.0}
    for mode in ("off", "rule_only", "rule_plus_rag"):
        print(f"\n--- mode={mode} ---")
        result = bridge_weather_dict(sample, scene="出行", mode=mode)
        text = result["semantic_text"] or "(空)"
        print(text)


if __name__ == "__main__":
    test_precipitation_grading()
    test_rag_enrichment()
    test_three_modes()
