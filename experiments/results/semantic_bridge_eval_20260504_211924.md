# 语义桥接评测报告

- 评测时间：20260504_211924
- 用例总数：**71**
- 评测档位：off, rule_only, rule_plus_rag, llm_baseline
- 评测集：`data/test_cases/semantic_bridge_bench.jsonl`

## 一、4 档消融总表

| 指标 | mode=off (baseline) | mode=rule_only | mode=rule_plus_rag | mode=llm_baseline |
|---|---|---|---|---|
| 覆盖率（生成 ≥1 label） | 0.0% | 100.0% | 100.0% | 74.6% |
| 标签条数一致 | 5.6% | 100.0% | 100.0% | 74.6% |
| 分级名准确率（grade） | 5.6% | 100.0% | 100.0% | 47.9% |
| 分级 ID 准确率（grade_id） | 5.6% | 100.0% | 100.0% | 5.6% |
| 引用率（must_cite 全中） | — | — | 100.0% | 25.4% |
| 场景过滤负例通过率 | — | — | 100.0% | 66.7% |
| source 字段匹配率 | — | — | 100.0% | 0.0% |
| baseline 文本为空率（off 专属） | 100.0% | — | — | — |
| citation 出现率（LLM baseline 专属） | — | — | — | 82.0% |
| citation 标准号真实性（LLM baseline 专属） | — | — | — | 72.0% |

## 二、按用例类别拆分

| 类别 | 用例数 | rule_only · grade_id | rule_plus_rag · grade_id | llm_baseline · grade_id | llm · cite真实 | rag · 引用率 |
|---|---|---|---|---|---|---|
| fallback | 4 | 100.0% | 100.0% | 100.0% | — | — |
| humidity | 8 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| multi | 3 | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% |
| precipitation_12h | 5 | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% |
| precipitation_24h | 11 | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% |
| scene_filter | 3 | 100.0% | 100.0% | 0.0% | 66.7% | — |
| temperature | 12 | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| visibility | 9 | 100.0% | 100.0% | 0.0% | — | 100.0% |
| wind | 16 | 100.0% | 100.0% | 0.0% | 100.0% | 100.0% |

## 三、失败用例

> mode=off 下**预期**全部非 fallback 用例覆盖率为 0%，是 baseline 设计目标，本节不重复展示其失败明细（详见关键结论部分的统计）。本节展示 rule_only / rule_plus_rag / llm_baseline 三档下**未达到期望**的用例。

### mode=llm_baseline（67 条）

- **rain24_001_trace** [precipitation_24h] 24h 微量降水 0.05mm（< 0.1）
  - input: `{"precip": "0.05mm"}`，scene: `None`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '微量降水（零星降水）', 'grade_id': 'trace', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 0.05mm → 微量降水（零星降水）\n  影响：降水量极微，地面几乎无积水，对出行和农业生产无实质影响。\n  依据：GB/T 28592-2012 §4.1（中国气象局）——24小时降水量＜0.1mm为微量降水，不构成小雨等级'`

- **rain24_002_light_low** [precipitation_24h] 24h 小雨下界 0.1mm
  - input: `{"precip": "0.1mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '小雨', 'grade_id': 'light_rain', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 0.1mm → 小雨\n  影响：路面微湿，出行需注意防滑，但对交通影响较小，可正常出行。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_003_light_mid** [precipitation_24h] 24h 小雨典型 5mm
  - input: `{"precip": "5mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '小雨', 'grade_id': 'light_rain', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 5mm → 小雨\n  影响：路面微湿，出行需携带雨具，对交通影响较小，但步行和骑行需注意路面湿滑。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_004_light_high** [precipitation_24h] 24h 小雨上界 9.9mm
  - input: `{"precip": "9.9mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '小雨', 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 9.9mm → 小雨\n  影响：路面微湿，出行基本不受影响，无需携带雨具但可备伞；驾车时注意轻微路滑。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_005_moderate_low** [precipitation_24h] 24h 中雨下界 10.0mm
  - input: `{"precip": "10mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '中雨', 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 10mm → 中雨\n  影响：出行时路面湿滑、有积水，能见度下降，建议携带雨具并注意交通安全，驾车需减速慢行。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_006_moderate_high** [precipitation_24h] 24h 中雨上界 24.9mm
  - input: `{"precip": "24.9mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '中雨', 'grade_id': 'moderate_rain', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 24.9mm → 中雨\n  影响：出行时路面湿滑、能见度下降，需携带雨具，驾车应减速慢行、注意防滑。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_007_heavy_low** [precipitation_24h] 24h 大雨下界 25.0mm
  - input: `{"precip": "25mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '大雨', 'grade_id': 'heavy_rain', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 25mm → 大雨\n  影响：24小时累积降水量达25mm，路面明显积水，能见度下降，出行需携带雨具，驾车应减速慢行、注意防滑，低洼路段易出现积水影响通行。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_008_heavy_typical** [precipitation_24h] 24h 大雨典型 35mm
  - input: `{"precip": "35mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '大雨', 'grade_id': 'heavy_rain', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 35mm → 大雨\n  影响：24小时累积降水量35mm，属大雨级别；出行时路面明显湿滑、低洼处易积水，能见度下降，驾车需减速慢行，步行注意防滑防溅。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_009_rainstorm** [precipitation_24h] 24h 暴雨 80mm
  - input: `{"precip": "80mm"}`，scene: `防汛`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '暴雨', 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 80mm → 暴雨\n  影响：24小时累积降水量达80mm，属暴雨级别，低洼地区易出现积水，城市内涝和山洪风险显著升高，需加强防汛巡查与排水调度。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_010_heavy_rainstorm** [precipitation_24h] 24h 大暴雨 200mm
  - input: `{"precip": "200mm"}`，scene: `防汛`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '大暴雨', 'grade_id': 'heavy_rainstorm', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 200mm → 大暴雨\n  影响：24小时累积降水量达200mm，属大暴雨级别，极易引发城市内涝、山洪、泥石流和滑坡等次生灾害，防汛形势严峻，需启动高级别防汛应急响应。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain24_011_extreme** [precipitation_24h] 24h 特大暴雨 300mm
  - input: `{"precip": "300mm"}`，scene: `防汛`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '特大暴雨', 'grade_id': '6', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 300mm → 特大暴雨\n  影响：24小时降水量达300mm属特大暴雨，可造成严重洪涝灾害、城市大面积内涝、山洪暴发及河流水位暴涨，对防汛形势构成极大威胁，需紧急启动防汛应急响应。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain12_001_light** [precipitation_12h] 12h 小雨上界 4.9mm
  - input: `{"precip_12h": "4.9mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_12h', 'grade': '小雨', 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_12h] 4.9mm → 小雨\n  影响：12小时累积降水4.9mm，属小雨量级；路面微湿，对出行有轻微影响，建议携带雨具、注意路面防滑。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain12_002_moderate** [precipitation_12h] 12h 中雨上界 14.9mm
  - input: `{"precip_12h": "14.9mm"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'precip_12h', 'grade': '中雨', 'grade_id': 'moderate_rain_12h', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_12h] 14.9mm → 中雨\n  影响：12小时累积降水14.9mm，已达中雨量级上限；路面湿滑、能见度下降，出行需携带雨具，驾车应减速慢行、注意防滑。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **rain12_003_heavy** [precipitation_12h] 12h 大雨 25mm
  - input: `{"precip_12h": "25mm"}`，scene: `出行`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **rain12_004_rainstorm** [precipitation_12h] 12h 暴雨 50mm
  - input: `{"precip_12h": "50mm"}`，scene: `防汛`
  - 实际 labels: `[{'variable': 'precip_12h', 'grade': '暴雨', 'grade_id': 'torrential_rain', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_12h] 50mm → 暴雨\n  影响：12小时累积降水量达50mm，属暴雨级别，极易引发城市内涝、山洪及中小河流洪水，防汛形势严峻，需加强巡查与应急响应。\n  依据：GB/T 28592-2012 §4.1 表1（中国气象局）'`

- **rain12_005_overflow** [precipitation_12h] 12h 超出表上限 100mm（应钳制为暴雨）
  - input: `{"precip_12h": "100mm"}`，scene: `防汛`
  - 实际 labels: `[{'variable': 'precip_12h', 'grade': '大暴雨', 'grade_id': 'heavy_rainstorm_12h', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_12h] 100mm → 大暴雨\n  影响：12小时累积降水量达100mm，属大暴雨级别，极易引发城市内涝、山洪、泥石流和中小河流洪水，防汛形势严峻，需立即启动应急响应并加强巡查排险。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **wind_000_calm** [wind] 风力 0 级 无风
  - input: `{"windScale": "0级"}`，scene: `航行`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '无风', 'grade_id': '0', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 0级 → 无风\n  影响：海面如镜，烟直上；帆船完全无风力可借，无法靠风推进，需靠机械动力或等待起风。\n  依据：GB/T 28591-2012 §4（中国气象局）'`

- **wind_001_light_air** [wind] 风力 1 级 软风
  - input: `{"windScale": "1级"}`，scene: `航行`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '软风', 'grade_id': '1', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 1级 → 软风\n  影响：风速0.3～1.5 m/s，炊烟可指示风向但风标不动；对航行几乎无影响，帆船难以借力前行，需依靠动力推进。\n  依据：GB/T 28591-2012 §4（风力等级表）'`

- **wind_002_light_breeze** [wind] 风力 2 级 轻风
  - input: `{"windScale": "2级"}`，scene: `户外`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '轻风', 'grade_id': '2', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 2级 → 轻风\n  影响：人面感觉有风，树叶微响，风向标能转动；户外活动基本不受影响，体感舒适。\n  依据：GB/T 28591-2012 §3（中国气象局）'`

- **wind_003_gentle** [wind] 风力 3 级 微风
  - input: `{"windScale": "3级"}`，scene: `户外`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '微风', 'grade_id': '3', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 3级 → 微风\n  影响：树叶及细枝摇动不息，旗帜展开；户外活动基本不受影响，风筝等轻物可被吹动。\n  依据：GB/T 28591-2012 §3 表1（中国气象局）'`

- **wind_004_moderate** [wind] 风力 4 级 和风
  - input: `{"windScale": "4级"}`，scene: `户外`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '和风', 'grade_id': '4', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 4级 → 和风\n  影响：能吹起地面灰尘和纸张，树的小枝摇动；户外活动需注意防风，轻便物品可能被吹落。\n  依据：GB/T 28591-2012 §4（中国气象局）'`

- **wind_005_fresh** [wind] 风力 5 级 清劲风
  - input: `{"windScale": "5级"}`，scene: `户外`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '清风', 'grade_id': '5', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 5级 → 清风\n  影响：5级清风可使小树摇摆、水面起波，户外活动受一定影响，高空作业及水上活动需注意防风。\n  依据：GB/T 28591-2012 §4 风力等级表（中国气象局）'`

- **wind_006_strong** [wind] 风力 6 级 强风（高空作业警戒）
  - input: `{"windScale": "6级"}`，scene: `高空作业`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '强风', 'grade_id': '6', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 6级 → 强风\n  影响：6级强风时大树枝摇动、电线有呼呼声，对高空作业构成显著安全威胁；根据建筑施工安全规范，6级及以上风力应停止露天高处作业。\n  依据：GB/T 28591-2012 §3（蒲福风级表）；JGJ 80-2016 §5.1.3（建筑施工高处作业安全技术规范：6级及以上大风应停止露天高处作业）'`

- **wind_007_near_gale** [wind] 风力 7 级 疾风（高空作业停止）
  - input: `{"windScale": "7级"}`，scene: `高空作业`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '疾风', 'grade_id': '7', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 7级 → 疾风\n  影响：7级疾风可致树木大幅摇摆、逆风行走困难；高空作业必须立即停止，存在人员坠落、工具物料飞落伤人的严重风险。\n  依据：GB/T 28591-2012 §4（风力等级表）；JGJ 80-2016 §5.1.6（高处作业遇6级及以上强风应停止作业）'`

- **wind_008_gale** [wind] 风力 8 级 大风
  - input: `{"windScale": "8级"}`，scene: `高空作业`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '大风', 'grade_id': '8', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 8级 → 大风\n  影响：8级大风风速达17.2~20.7 m/s，对高空作业极为危险，易导致人员失稳坠落、设施倾覆，必须立即停止一切高空作业。\n  依据：GB/T 28591-2012 §4（风力等级表）；JGJ 80-2016 §3.0.3（高处作业遇6级及以上强风必须停止）'`

- **wind_009_strong_gale** [wind] 风力 9 级 烈风
  - input: `{"windScale": "9级"}`，scene: `应急`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '烈风', 'grade_id': '9', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 9级 → 烈风\n  影响：9级烈风可导致建筑物轻微受损，屋顶瓦片被掀起，树枝折断，对户外作业、水上交通及高空作业构成严重威胁，应急场景下需立即停止户外危险作业并加固临时设施。\n  依据：GB/T 28591-2012 §4（中国气象局）'`

- **wind_010_storm** [wind] 风力 10 级 狂风
  - input: `{"windScale": "10级"}`，scene: `应急`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '狂风', 'grade_id': '10', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 10级 → 狂风\n  影响：陆上极少见，可拔起树木、摧毁建筑物，对人员安全和基础设施构成严重威胁，应急场景下需立即启动防风避险响应。\n  依据：GB/T 28591-2012 §3（风力等级表）'`

- **wind_011_violent_storm** [wind] 风力 11 级 暴风
  - input: `{"windScale": "11级"}`，scene: `应急`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '暴风', 'grade_id': '11', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 11级 → 暴风\n  影响：陆上极少见，可造成大范围严重破坏，建筑物严重受损，树木被连根拔起，交通中断，属极端灾害性天气，应急场景下需立即启动防风抢险响应。\n  依据：GB/T 28591-2012 §4（风力等级表）'`

- **wind_012_hurricane** [wind] 风力 12 级 飓风
  - input: `{"windScale": "12级"}`，scene: `应急`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '飓风', 'grade_id': '12', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 12级 → 飓风\n  影响：摧毁力极大，陆上极少见，建筑物可遭严重损毁，树木连根拔起，车辆被掀翻，对应急响应构成极端威胁，需启动最高级别防风应急响应。\n  依据：GB/T 28591-2012 §4（中国气象局）'`

- **wind_013_range_field** [wind] 和风范围字段 1-3级（取上界 → 微风）
  - input: `{"windScaleDay": "1-3级"}`，scene: `户外`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '微风', 'grade_id': '3', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 1-3级 → 微风\n  影响：旗帜开始飘动，树叶和细枝摇动不息；户外活动基本不受影响，体感舒适。\n  依据：GB/T 28591-2012 §4（风力等级表）'`

- **wind_014_int_field** [wind] 整数字段 windScale=8
  - input: `{"windScale": 8}`，scene: `高空作业`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '大风', 'grade_id': '8', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 8级 → 大风\n  影响：8级大风对高空作业极为危险，可导致人员失稳坠落、结构物摇晃，应立即停止一切露天高空作业。\n  依据：GB/T 28591-2012 §3（风力等级）；JGJ 80-2016 §3.0.5（高处作业遇6级及以上强风必须停止作业）'`

- **wind_015_overflow** [wind] 风力越界 15 级（钳制为飓风）
  - input: `{"windScale": "15级"}`，scene: `应急`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '15级（超强台风级风力）', 'grade_id': '15', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 15级 → 15级（超强台风级风力）\n  影响：极端破坏性风力，可摧毁房屋建筑、掀翻车辆、连根拔起大树，对人员生命安全构成极严重威胁；应急场景下需立即启动最高级别防风响应，停止一切户外活动。\n  依据：GB/T 28591-2012 §4（中国气象局）；GB/T 19201-2006 §3（热带气旋等级）'`

- **scene_001_rain_offscene** [scene_filter] 大雨 + scene=高空作业（不在大雨 applicable_scene 内 → 不富化）
  - input: `{"precip": "35mm"}`，scene: `高空作业`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '大雨', 'grade_id': 'heavy_rain', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 35mm → 大雨\n  影响：24小时累积降水量达35mm，属大雨级别；高空作业时能见度下降、平台湿滑、风力叠加降雨影响显著，极易发生坠落和滑倒事故，应停止露天高空作业。\n  依据：GB/T 28592-2012 §4.1（中国气象局）'`

- **scene_002_wind7_offscene** [scene_filter] 7 级风 + scene=出行（不在 7 级 applicable_scene 内 → 不富化）
  - input: `{"windScale": "7级"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'wind_scale', 'grade': '疾风', 'grade_id': '7', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[wind_scale] 7级 → 疾风\n  影响：全树摇动，迎风步行感到困难；出行时骑行、步行均受明显影响，高空作业及水上交通需暂停。\n  依据：GB/T 28591-2012 §4（中国气象局）'`

- **multi_001_rain_wind** [multi] 多要素：大雨 + 7 级疾风 + scene=施工 → 两条都富化
  - input: `{"precip": "35mm", "windScale": "7级"}`，scene: `施工`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '大雨', 'grade_id': 'heavy_rain', 'source': 'llm_baseline'}, {'variable': 'wind_scale', 'grade': '疾风', 'grade_id': '7', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 35mm → 大雨\n  影响：露天施工受严重影响，土方开挖及混凝土浇筑应暂停，需加强基坑排水和边坡防护，防止积水与滑坡。\n  依据：GB/T 28592-2012 §4.1（中国气象局）\n\n[wind_scale] 7级 → 疾风\n  影响：禁止塔吊等起重机械作业及高空施工作业，脚手架和临时围挡需加固，现场人员应撤离至安全区域。\n  依据：GB/T 28591-2012 '`

- **multi_002_rain12_wind** [multi] 多要素：12h 大雨 + 5 级风 + scene=施工（两者 applicable_scene 交集）
  - input: `{"precip_12h": "25mm", "windScale": "5级"}`，scene: `施工`
  - 实际 labels: `[{'variable': 'precip_12h', 'grade': '大雨', 'grade_id': 'heavy_rain_12h', 'source': 'llm_baseline'}, {'variable': 'wind_scale', 'grade': '清风（劲风）', 'grade_id': 'beaufort_5', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_12h] 25mm → 大雨\n  影响：露天施工应暂停，土方开挖及混凝土浇筑等作业受严重影响，需加强基坑排水和边坡防涝措施。\n  依据：GB/T 28592-2012 §4 表1（中国气象局）\n\n[wind_scale] 5级 → 清风（劲风）\n  影响：高空作业及塔吊吊装应停止，脚手架及临时围挡需加固，露天材料需防风绑扎。\n  依据：GB/T 28591-2012 §4 表1（中'`

- **temp_001_cold_extreme** [temperature] 严寒 -15℃
  - input: `{"temp": "-15°C"}`，scene: `户外作业`
  - 实际 labels: `[{'variable': 'temp', 'grade': '低温作业Ⅲ级', 'grade_id': 'cold_work_3', 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] -15°C → 低温作业Ⅲ级\n  影响：-15°C 户外作业存在中度冻伤与失温风险，手部灵活性显著下降，应缩短连续暴露时间、加强防寒保暖并安排轮换休息。\n  依据：GB/T 14440-1993 §3（国家技术监督局）'`

- **temp_002_cold_upper** [temperature] 寒冷上界 -0.1℃
  - input: `{"temp": "-0.1°C"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'temp', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] -0.1°C\n  影响：气温低于0°C，路面可能出现结冰或暗冰，出行需注意防滑、减速慢行，尤其是桥梁和背阴路段。'`

- **temp_003_chilly_low** [temperature] 偏冷下界 0℃
  - input: `{"temp": "0°C"}`，scene: `出行`
  - 实际 labels: `[{'variable': 'temp', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] 0°C'`

- **temp_004_chilly_typical** [temperature] 偏冷典型 5℃
  - input: `{"temp": "5°C"}`，scene: `穿衣建议`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **temp_005_cool** [temperature] 凉爽典型 15℃
  - input: `{"temp": "15°C"}`，scene: `运动`
  - 实际 labels: `[{'variable': 'temp', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] 15°C'`

- **temp_006_comfortable_low** [temperature] 舒适下界 18℃
  - input: `{"temp": "18°C"}`，scene: `生活`
  - 实际 labels: `[{'variable': 'temp', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] 18°C'`

- **temp_007_comfortable_high** [temperature] 舒适上界 23.9℃
  - input: `{"temp": "23.9°C"}`，scene: `生活`
  - 实际 labels: `[{'variable': 'temp', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] 23.9°C'`

- **temp_008_warm** [temperature] 温暖 28℃
  - input: `{"temp": "28°C"}`，scene: `穿衣建议`
  - 实际 labels: `[{'variable': 'temp', 'grade': '热', 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] 28°C → 热\n  影响：气温较高，建议穿着轻薄透气的短袖、短裤等夏装，户外活动注意防晒防暑。\n  依据：GB/T 35228-2017 §5（中国气象局）'`

- **temp_009_hot** [temperature] 炎热 32℃
  - input: `{"temp": "32°C"}`，scene: `户外作业`
  - 实际 labels: `[{'variable': 'temp', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] 32°C\n  影响：32°C未达到气象高温预警阈值（≥35°C），但在户外作业场景下长时间暴露仍有中暑风险，建议增加饮水与休息频次、避免正午时段连续作业。\n  依据：《防暑降温措施管理办法》安监总安健〔2012〕89号 §5、§8（国家安全生产监督管理总局等）；高温预警信号标准见《气象灾害预警信号发布与传播办法》中国气象局令第16号 §附录（中国气象局）'`

- **temp_010_high_yellow** [temperature] 高温黄色预警门槛 35℃
  - input: `{"temp": "35°C"}`，scene: `户外作业`
  - 实际 labels: `[{'variable': 'temp', 'grade': '高温黄色预警', 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[temp] 35°C → 高温黄色预警\n  影响：日最高气温≥35°C，户外作业人员中暑风险显著升高，应减少连续作业时间、增加休息频次并采取防暑降温措施。\n  依据：中国气象局《气象灾害预警信号发布与传播办法》(2007) 附则·高温预警信号'`

- **temp_011_high_red** [temperature] 高温红色预警门槛 40℃
  - input: `{"temp": "40°C"}`，scene: `应急`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **temp_012_alias_feelslike** [temperature] 别名字段 feelsLike=-5℃
  - input: `{"feelsLike": "-5°C"}`，scene: `出行`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_001_extreme** [visibility] 极端低能见度 30m
  - input: `{"visibility": 30}`，scene: `驾驶`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_002_heavy_dense_fog** [visibility] 强浓雾 100m
  - input: `{"visibility": 100}`，scene: `驾驶`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_003_dense_fog** [visibility] 浓雾 300m
  - input: `{"visibility": 300}`，scene: `高空作业`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_004_fog** [visibility] 雾 800m
  - input: `{"visibility": 800}`，scene: `驾驶`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_005_mist** [visibility] 轻雾/轻霾 3000m
  - input: `{"visibility": 3000}`，scene: `驾驶`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_006_good** [visibility] 良好 7000m
  - input: `{"visibility": 7000}`，scene: `驾驶`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_007_excellent** [visibility] 极佳 15km
  - input: `{"visibility": 15000}`，scene: `出行`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_008_alias_vis_km** [visibility] 和风字段 vis=0.4 (km) → 400 m 浓雾
  - input: `{"vis": "0.4"}`，scene: `驾驶`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **vis_009_alias_vis_int** [visibility] 和风整数字段 vis=25 (km) → 25 km 极佳
  - input: `{"vis": 25}`，scene: `出行`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **hum_001_very_dry** [humidity] 极干燥 20%
  - input: `{"humidity": "20%"}`，scene: `健康`
  - 实际 labels: `[{'variable': 'humidity', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[humidity] 20%\n  影响：相对湿度20%远低于人体舒适下限（30%），空气极度干燥，易导致皮肤干裂、呼吸道黏膜受损、咽喉不适，显著增加呼吸道感染风险，在健康场景下需重点关注。\n  依据：GB/T 18883-2022 §4.2（国家市场监督管理总局/国家卫生健康委员会）'`

- **hum_002_dry** [humidity] 干燥 35%
  - input: `{"humidity": "35%"}`，scene: `健康`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **hum_003_comfort** [humidity] 适宜下界 40%
  - input: `{"humidity": "40%"}`，scene: `生活`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **hum_004_comfort_upper** [humidity] 适宜上界 60%
  - input: `{"humidity": "60%"}`，scene: `生活`
  - 实际 labels: `[{'variable': 'humidity', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[humidity] 60%'`

- **hum_005_humid** [humidity] 偏湿 70%
  - input: `{"humidity": "70%"}`，scene: `生活`
  - 实际 labels: `[{'variable': 'humidity', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[humidity] 70%'`

- **hum_006_very_humid** [humidity] 潮湿 85%
  - input: `{"humidity": "85%"}`，scene: `户外作业`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **hum_007_extreme** [humidity] 极潮湿 95%
  - input: `{"humidity": "95%"}`，scene: `户外作业`
  - 实际 labels: `[{'variable': 'humidity', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[humidity] 95%'`

- **hum_008_alias_rh** [humidity] 别名字段 rh=50 → 适宜
  - input: `{"rh": 50}`，scene: `生活`
  - 实际 labels: `[]`
  - 实际文本前 200 字：`''`

- **multi_003_five_elements** [multi] 5 类要素同输入：大雨+7级风+凉爽17℃+浓雾400m+潮湿85%（scene=施工）
  - input: `{"temp": "17°C", "precip": "35mm", "windScale": "7级", "vis": "0.4", "humidity": "85%"}`，scene: `施工`
  - 实际 labels: `[{'variable': 'precip_24h', 'grade': '大雨', 'grade_id': None, 'source': 'llm_baseline'}, {'variable': 'wind_scale', 'grade': '疾风', 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[precip_24h] 35mm → 大雨\n  影响：施工场景下，工地易积水，露天混凝土浇筑和土方作业应暂停，需加强基坑排水与边坡稳定监测。\n  依据：GB/T 28592-2012 §4.1（中国气象局）\n\n[wind_scale] 7级 → 疾风\n  影响：施工场景下，7级风对高空作业和塔吊运行构成安全威胁，应停止露天攀登、悬空等高处作业，并加固临时设施和围挡。\n  依据：GB/T 2859'`

- **scene_003_humid_offscene** [scene_filter] 潮湿 85% + scene=航行（不在 applicable_scene 内 → 不富化）
  - input: `{"humidity": "85%"}`，scene: `航行`
  - 实际 labels: `[{'variable': 'humidity', 'grade': None, 'grade_id': None, 'source': 'llm_baseline'}]`
  - 实际文本前 200 字：`'[humidity] 85%'`

备注：mode=off 在 67 条非 fallback 用例上 **累计未达期望** 67 条 （67/67 = 100%），构成消融对照的负参照。

## 四、关键结论（自动摘要）

- **确定性分级覆盖**：rule_only 模式下 grade_id 准确率 100.0%，证明分类器表的阈值划分覆盖了所有有效输入。
- **权威引用注入**：rule_plus_rag 模式下 must_cite 关键字命中率 100.0%，证明 grade_id 硬链接能稳定从 KB 召回出处条款；场景不匹配时正确退化为 rule_only，不输出无关 citation。
- **baseline 对照**：mode=off 时 semantic_text 为空率 100.0%，完全依赖 LLM 自由发挥处理裸数值，作为消融实验的负参照。
- **LLM 自由发挥（无桥接）**：grade 名准确率 47.9%、grade_id 准确率 5.6%（凭印象编 ID 几乎不可能与 KB 命名一致）；citation 出现率 82.0%（LLM 几乎都给出了一段 citation），其中**包含真实存在标准号的比率 72.0%**（粗粒度幻觉检测）；must_cite 关键字命中率 25.4%（与 KB 完全一致的严格命中率），source 字段升级率 0.0%。
- **关键观察**：LLM baseline 在 grade 名上有相当能力（凭内置常识可推断“35mm = 大雨”这类典型分级），但在**严格的标准编号 + 条款号**上呈现典型幻觉模式：标准号对、条款号错；或张冠李戴用相邻标准。这与`docs/写作文档/知识库标准核对表-论文素材.md` 中我们对种子数据做人工核对时发现的同类错误一一对应。
