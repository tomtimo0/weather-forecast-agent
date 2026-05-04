"""第二步验收脚本：风力分类器 + KB 风级条目 + 端到端桥接

测试覆盖：
1. ``classify_wind_scale`` 在 0–12 级、越界、非法值上的行为
2. ``parse_wind_scale`` 对和风天气各种字段格式（"7级"/"1-3级"）的解析
3. KB 中 grading_wind_beaufort_0..12 全部 13 条均存在且能被 ``get_by_id`` 命中
4. ``bridge_weather_dict`` 在多字段输入（precip + windScale）下的端到端输出，
   包含正确的 grade / citation / impact
"""

from __future__ import annotations

from src.analysis.classifiers.wind_scale import (
    WIND_BEAUFORT_GRADES,
    classify_wind_scale,
    parse_wind_scale,
)
from src.analysis.semantic_bridge import bridge_weather_dict
from src.rag.knowledge_base import get_knowledge_base


def test_classify_wind_scale() -> None:
    """0–12 级及越界、非法值的分级行为。"""
    cases = [
        (0, "无风", "grading_wind_beaufort_0", None),
        (1, "软风", "grading_wind_beaufort_1", None),
        (4, "和风", "grading_wind_beaufort_4", None),
        (7, "疾风", "grading_wind_beaufort_7", None),
        (12, "飓风", "grading_wind_beaufort_12", None),
        (15, "飓风", "grading_wind_beaufort_12", "上限"),
    ]
    for scale, expect_grade, expect_id, expect_note_kw in cases:
        lbl = classify_wind_scale(scale)
        assert lbl.grade == expect_grade, f"scale={scale} 期望 {expect_grade}，实际 {lbl.grade}"
        assert lbl.grade_id == expect_id, f"scale={scale} grade_id 不符"
        if expect_note_kw:
            assert lbl.note and expect_note_kw in lbl.note, f"scale={scale} note 异常"
        else:
            assert lbl.note is None, f"scale={scale} 不应有 note，实际 {lbl.note}"

    nan_lbl = classify_wind_scale(None)
    assert nan_lbl.grade is None and nan_lbl.source == "fallback"

    neg_lbl = classify_wind_scale(-1)
    assert neg_lbl.grade is None and neg_lbl.source == "fallback"
    print("[OK] classify_wind_scale 0-12/越界/非法值 全部通过")


def test_parse_wind_scale() -> None:
    """和风天气字段格式解析。"""
    assert parse_wind_scale("7") == 7
    assert parse_wind_scale("7级") == 7
    assert parse_wind_scale("1-3级") == 3, "范围应取上界"
    assert parse_wind_scale("1~3") == 3
    assert parse_wind_scale(7) == 7
    assert parse_wind_scale(7.0) == 7
    assert parse_wind_scale(None) is None
    assert parse_wind_scale("abc") is None
    assert parse_wind_scale("") is None
    print("[OK] parse_wind_scale 各种格式 全部通过")


def test_kb_has_all_wind_grades() -> None:
    """知识库 13 个风级条目全部入库。"""
    kb = get_knowledge_base()
    missing = []
    for grade_int, name, _lo, _hi, gid in WIND_BEAUFORT_GRADES:
        entry = kb.get_by_id(gid)
        if entry is None:
            missing.append(gid)
        else:
            assert name in entry.title, f"{gid} 标题不含名称 {name}"
    assert not missing, f"缺失的风力条目：{missing}"
    print(f"[OK] KB 13 个风级条目全部命中（grading_wind_beaufort_0..12）")


def test_bridge_end_to_end() -> None:
    """端到端：模拟和风 get_current_weather 返回，桥接后应同时含降水 + 风力两段。

    用 scene="施工"，因为大雨条目的 applicable_scene=[出行,施工,农业,防汛]
    与 7 级疾风条目的 applicable_scene=[航行,施工,高空作业,户外] 都覆盖该场景，
    确保两条都被富化（含 citation）。
    """
    sample = {"temp": "17°C", "precip": "35mm", "windScale": "7级"}
    result = bridge_weather_dict(sample, scene="施工", mode="rule_plus_rag")

    assert result["mode"] == "rule_plus_rag"
    labels = result["labels"]
    assert len(labels) == 2, f"应有 2 条标签（降水+风力），实际 {len(labels)}"

    by_var = {lbl.variable: lbl for lbl in labels}
    assert "precip_24h" in by_var and by_var["precip_24h"].grade == "大雨"
    assert "wind_scale" in by_var and by_var["wind_scale"].grade == "疾风"

    text = result["semantic_text"]
    assert "大雨" in text and "疾风" in text
    assert "GB/T 28592-2012" in text, "降水应引用国标"
    assert "Beaufort" in text or "蒲福" in text, "风力应引用蒲福风级"
    print("[OK] 端到端桥接（precip + wind）输出包含两类等级与对应出处")
    print()
    print("--- 实际语义文本 ---")
    print(text)


def test_bridge_range_wind_scale() -> None:
    """逐日预报 windScaleDay='1-3级' 这种范围字段也应被正确处理。"""
    sample = {"windScaleDay": "1-3级"}
    result = bridge_weather_dict(sample, mode="rule_only")
    labels = result["labels"]
    assert len(labels) == 1
    assert labels[0].variable == "wind_scale"
    assert labels[0].grade == "微风", f"1-3级 应取上界 → 3 级微风，实际 {labels[0].grade}"
    print("[OK] 范围字段（1-3级）取上界 → 微风")


if __name__ == "__main__":
    test_classify_wind_scale()
    test_parse_wind_scale()
    test_kb_has_all_wind_grades()
    test_bridge_range_wind_scale()
    test_bridge_end_to_end()
    print()
    print("=== 第二步全部测试通过 ===")
