"""扩展分类器（温度 / 能见度 / 湿度）+ 端到端桥接验收脚本

测试覆盖：
1. 三个分类器各自的关键阈值与边界（含越界、缺失、非法）
2. 三个分类器的 ``parse_*`` 在工具层字段格式上的解析（``"17°C"`` /
   ``"5 km"`` / ``"50%"`` / 纯数值等）
3. KB 中 grading_temperature / visibility / humidity 全部 18 条新条目
   均存在且能被 ``get_by_id`` 命中
4. ``bridge_weather_dict`` 在 5 类要素同时存在的 dict 输入下端到端跑通，
   产出 5 条 SemanticLabel（按场景过滤后含 citation）
"""

from __future__ import annotations

from src.analysis.classifiers.humidity import (
    HUMIDITY_GRADES,
    classify_humidity,
    parse_humidity,
)
from src.analysis.classifiers.temperature import (
    TEMPERATURE_GRADES,
    classify_temperature,
    parse_temperature,
)
from src.analysis.classifiers.visibility import (
    VISIBILITY_GRADES,
    classify_visibility,
    parse_visibility,
)
from src.analysis.semantic_bridge import bridge_weather_dict
from src.rag.knowledge_base import get_knowledge_base


# ---------------------------------------------------------------------------
# 温度
# ---------------------------------------------------------------------------

def test_classify_temperature_thresholds() -> None:
    """覆盖每档下界 / 上界 / 中点。"""
    cases = [
        (-15.0, "寒冷", "grading_temperature_cold"),
        (-0.1,  "寒冷", "grading_temperature_cold"),
        (0.0,   "偏冷", "grading_temperature_chilly"),
        (9.9,   "偏冷", "grading_temperature_chilly"),
        (10.0,  "凉爽", "grading_temperature_cool"),
        (17.9,  "凉爽", "grading_temperature_cool"),
        (18.0,  "舒适", "grading_temperature_comfortable"),
        (23.9,  "舒适", "grading_temperature_comfortable"),
        (24.0,  "温暖", "grading_temperature_warm"),
        (29.9,  "温暖", "grading_temperature_warm"),
        (30.0,  "炎热", "grading_temperature_hot"),
        (34.9,  "炎热", "grading_temperature_hot"),
        (35.0,  "高温", "grading_temperature_high_warning"),
        (40.0,  "高温", "grading_temperature_high_warning"),
    ]
    for v, expect_grade, expect_id in cases:
        lbl = classify_temperature(v)
        assert lbl.grade == expect_grade, f"{v}℃ 期望 {expect_grade}，实际 {lbl.grade}"
        assert lbl.grade_id == expect_id, f"{v}℃ grade_id 不符"

    nan_lbl = classify_temperature(None)
    assert nan_lbl.grade is None and nan_lbl.source == "fallback"
    print("[OK] classify_temperature 7 档边界 + 缺失 全部通过")


def test_parse_temperature() -> None:
    assert parse_temperature(17) == 17.0
    assert parse_temperature(17.5) == 17.5
    assert parse_temperature("17°C") == 17.0
    assert parse_temperature("17.5℃") == 17.5
    assert parse_temperature("-3°C") == -3.0
    assert parse_temperature("17 度") == 17.0
    assert parse_temperature("17") == 17.0
    assert parse_temperature("abc") is None
    assert parse_temperature(None) is None
    print("[OK] parse_temperature 多格式解析 全部通过")


# ---------------------------------------------------------------------------
# 能见度
# ---------------------------------------------------------------------------

def test_classify_visibility_thresholds() -> None:
    cases = [
        (0.0,        "极端低能见度",  "grading_visibility_extreme"),
        (49.9,       "极端低能见度",  "grading_visibility_extreme"),
        (50.0,       "强浓雾",        "grading_visibility_heavy_dense_fog"),
        (199.9,      "强浓雾",        "grading_visibility_heavy_dense_fog"),
        (200.0,      "浓雾",          "grading_visibility_dense_fog"),
        (499.9,      "浓雾",          "grading_visibility_dense_fog"),
        (500.0,      "雾",            "grading_visibility_fog"),
        (999.9,      "雾",            "grading_visibility_fog"),
        (1000.0,     "轻雾/轻霾",     "grading_visibility_mist"),
        (4999.9,     "轻雾/轻霾",     "grading_visibility_mist"),
        (5000.0,     "良好",          "grading_visibility_good"),
        (9999.9,     "良好",          "grading_visibility_good"),
        (10000.0,    "极佳",          "grading_visibility_excellent"),
        (50000.0,    "极佳",          "grading_visibility_excellent"),
    ]
    for v, expect_grade, expect_id in cases:
        lbl = classify_visibility(v)
        assert lbl.grade == expect_grade, f"{v}m 期望 {expect_grade}，实际 {lbl.grade}"
        assert lbl.grade_id == expect_id, f"{v}m grade_id 不符"

    miss = classify_visibility(None)
    assert miss.grade is None and miss.source == "fallback"
    neg = classify_visibility(-100.0)
    assert neg.grade is None and neg.source == "fallback"
    print("[OK] classify_visibility 7 档边界 + 缺失/非法 全部通过")


def test_parse_visibility() -> None:
    assert parse_visibility(800, unit="m") == 800.0
    assert parse_visibility(5, unit="km") == 5000.0
    assert parse_visibility("800m") == 800.0
    assert parse_visibility("5 km") == 5000.0
    assert parse_visibility("0.4 km") == 400.0
    assert parse_visibility(None) is None
    print("[OK] parse_visibility m/km 双单位 全部通过")


# ---------------------------------------------------------------------------
# 湿度
# ---------------------------------------------------------------------------

def test_classify_humidity_thresholds() -> None:
    cases = [
        (0.0,    "极干燥", "grading_humidity_very_dry"),
        (29.9,   "极干燥", "grading_humidity_very_dry"),
        (30.0,   "干燥",   "grading_humidity_dry"),
        (39.9,   "干燥",   "grading_humidity_dry"),
        (40.0,   "适宜",   "grading_humidity_comfort"),
        (60.0,   "适宜",   "grading_humidity_comfort"),
        (60.1,   "偏湿",   "grading_humidity_humid"),
        (75.0,   "偏湿",   "grading_humidity_humid"),
        (75.1,   "潮湿",   "grading_humidity_very_humid"),
        (89.9,   "潮湿",   "grading_humidity_very_humid"),
        (90.0,   "极潮湿", "grading_humidity_extreme"),
        (100.0,  "极潮湿", "grading_humidity_extreme"),
    ]
    for v, expect_grade, expect_id in cases:
        lbl = classify_humidity(v)
        assert lbl.grade == expect_grade, f"{v}% 期望 {expect_grade}，实际 {lbl.grade}"
        assert lbl.grade_id == expect_id, f"{v}% grade_id 不符"

    miss = classify_humidity(None)
    assert miss.grade is None and miss.source == "fallback"
    over = classify_humidity(150.0)
    assert over.grade is None and over.source == "fallback", "湿度 > 100 应判 fallback"
    print("[OK] classify_humidity 6 档边界 + 缺失/越界 全部通过")


def test_parse_humidity() -> None:
    assert parse_humidity(50) == 50.0
    assert parse_humidity(50.5) == 50.5
    assert parse_humidity("50%") == 50.0
    assert parse_humidity("65 %") == 65.0
    assert parse_humidity(None) is None
    assert parse_humidity("abc") is None
    print("[OK] parse_humidity 多格式 全部通过")


# ---------------------------------------------------------------------------
# KB 完整性
# ---------------------------------------------------------------------------

def test_kb_has_all_extended_grades() -> None:
    kb = get_knowledge_base()
    missing = []
    for table in (TEMPERATURE_GRADES, VISIBILITY_GRADES, HUMIDITY_GRADES):
        for row in table:
            gid = row[3]
            entry = kb.get_by_id(gid)
            if entry is None:
                missing.append(gid)
    assert not missing, f"缺失的 KB 条目：{missing}"
    n = len(TEMPERATURE_GRADES) + len(VISIBILITY_GRADES) + len(HUMIDITY_GRADES)
    print(f"[OK] KB 中 {n} 条 temperature/visibility/humidity 分级条目全部命中")


# ---------------------------------------------------------------------------
# 端到端桥接：5 类要素同时桥接
# ---------------------------------------------------------------------------

def test_bridge_end_to_end_five_elements() -> None:
    """场景=施工，5 类要素同输入 → 应得 5 条 SemanticLabel。

    选 scene="施工" 是因为施工对所有 5 类要素都有 applicable_scene 命中：
    - 大雨：[出行,施工,农业,防汛]   ← 命中
    - 7 级疾风：[航行,施工,高空作业,户外] ← 命中
    - 凉爽 17℃：[生活,出行,运动,穿衣建议,农业] —— **不**含施工
    - 浓雾 400m：[驾驶,航行,出行,施工,高空作业,应急] ← 命中
    - 潮湿 85%：[生活,健康,施工,户外作业]    ← 命中

    所以严格的"全 5 条都富化"不一定满足；本测试只断言：
    - 5 条 label 全部产出
    - 至少 4 条富化为 rule_plus_rag（凉爽 17℃ 由于场景过滤会保持 rule_only）
    - 各 label 的 grade 与 grade_id 与设计表一致
    """
    sample = {
        "temp": "17°C",
        "precip": "35mm",
        "windScale": "7级",
        "vis": "0.4",       # km → 400 m
        "humidity": "85%",
    }
    result = bridge_weather_dict(sample, scene="施工", mode="rule_plus_rag")
    labels = result["labels"]
    assert len(labels) == 5, f"应有 5 条 label，实际 {len(labels)}"

    by_var = {lbl.variable: lbl for lbl in labels}
    assert by_var["precip_24h"].grade == "大雨" and by_var["precip_24h"].grade_id == "grading_precip_24h_heavy"
    assert by_var["wind_scale"].grade == "疾风" and by_var["wind_scale"].grade_id == "grading_wind_beaufort_7"
    assert by_var["temp"].grade == "凉爽" and by_var["temp"].grade_id == "grading_temperature_cool"
    assert by_var["visibility"].grade == "浓雾" and by_var["visibility"].grade_id == "grading_visibility_dense_fog"
    assert by_var["humidity"].grade == "潮湿" and by_var["humidity"].grade_id == "grading_humidity_very_humid"

    enriched = sum(1 for lbl in labels if lbl.source == "rule_plus_rag")
    assert enriched >= 4, f"至少 4 条应富化（实际 {enriched} 条）"

    text = result["semantic_text"]
    assert "大雨" in text and "疾风" in text and "凉爽" in text
    assert "浓雾" in text and "潮湿" in text
    print(f"[OK] 端到端 5 类要素：5 条 label 全部产出，富化 {enriched}/5 条")
    print()
    print("--- 实际语义文本 ---")
    print(text)


def test_bridge_alias_field_names() -> None:
    """字段别名调度：visibility（米）/ vis（千米）/ rh（湿度别名）等。"""
    a = bridge_weather_dict({"visibility": 200}, mode="rule_only")
    assert len(a["labels"]) == 1 and a["labels"][0].grade == "浓雾"

    b = bridge_weather_dict({"vis": "0.2"}, mode="rule_only")  # 0.2 km = 200 m
    assert len(b["labels"]) == 1 and b["labels"][0].grade == "浓雾"

    c = bridge_weather_dict({"rh": 50}, mode="rule_only")
    assert len(c["labels"]) == 1 and c["labels"][0].grade == "适宜"

    d = bridge_weather_dict({"feelsLike": "-5°C"}, mode="rule_only")
    assert len(d["labels"]) == 1 and d["labels"][0].grade == "寒冷"
    print("[OK] 字段别名调度（visibility/vis/rh/feelsLike）全部通过")


if __name__ == "__main__":
    test_classify_temperature_thresholds()
    test_parse_temperature()
    test_classify_visibility_thresholds()
    test_parse_visibility()
    test_classify_humidity_thresholds()
    test_parse_humidity()
    test_kb_has_all_extended_grades()
    test_bridge_alias_field_names()
    test_bridge_end_to_end_five_elements()
    print()
    print("=== 扩展分类器全部测试通过 ===")
