# 基于大语言模型的气象预报数据检索与分析智能体

> 华中科技大学 · 数学与统计学院 · 信息与计算科学专业 · 2025–2026 毕业设计

基于 ReAct 范式构建的单智能体系统，把口语化气象查询自动转化为结构化 API 调用，
通过 **双通路 RAG**（混合检索 + 确定性分级器）与 **代码生成 + 受限沙箱**
两套机制，把异构数据接入、专业术语桥接与统计计算从"靠模型猜"转为
"靠工具学习与外部组件兜底"，从源头消解大语言模型在气象任务中的引用编造、
分级编造、数值漂移等典型幻觉。

---

## 系统架构

![系统技术路线](./技术路线.drawio.png)

完整论文详见 `docs/写作文档/论文.pdf`，对应章节：

| 章 | 内容 |
|---|---|
| 第 2 章 | ReAct 范式 + RAG + Prompt 策略 |
| 第 3 章 | 异构 API 统一封装 + 双阶段 NLU 管线 |
| 第 4 章 | 双通路 RAG（语义桥接） + 代码生成沙箱 |
| 第 5 章 | 5 份评测集 214 条用例的系统化实证 |

---

## 目录结构

```text
d:\毕设\
├── README.md                  # 本文件
├── 技术路线.drawio.png        # 系统技术路线图
├── src/                       # 源代码
│   ├── agent/                 # ReAct Agent 主控（含意图前置、多轮记忆）
│   ├── intent/                # 双阶段 NLU：意图识别 + 参数补全
│   ├── tools/                 # 11 个工具单元（9 气象 + 2 RAG/桥接 + 沙箱）
│   ├── rag/                   # 混合检索（向量 + BM25）+ ChromaDB 持久化
│   ├── analysis/              # 语义桥接（5 类分级器 + grade_id 硬链接 + 富化器）
│   │   ├── classifiers/       # precip / wind / temperature / visibility / humidity
│   │   ├── enrichers/         # rag_enricher（按 grade_id 精确查 KB）
│   │   ├── code_generator.py  # LLM 生成 compute(data) 函数
│   │   └── semantic_bridge.py # 桥接入口（off / rule_only / rule_plus_rag）
│   └── config/                # 配置（settings.py 含密钥，已 .gitignore）
├── data/
│   ├── knowledge/             # RAG 知识库（62 条，覆盖 17 项国标 / 行标）
│   └── test_cases/            # 5 份评测集 jsonl 共 214 条用例
├── experiments/
│   ├── eval/                  # 5 套独立评测脚本 + 共 baseline 脚本
│   └── results/               # 评测结果（json + markdown 双输出 + 三层缓存）
├── tests/                     # 单元测试
└── docs/写作文档/             # 论文 LaTeX 源、图素材、论文素材文档、开发日志
```

---

## 快速开始

```bash
# 1. 创建并激活环境
conda create -n weather311 python=3.11
conda activate weather311

# 2. 安装核心依赖
pip install langchain langchain-openai langgraph requests
pip install chromadb rank_bm25 pydantic

# 3. 配置 API 密钥
#    复制 src/config/settings.example.py 为 src/config/settings.py，填入：
#      LLM_MODEL / LLM_API_KEY / LLM_BASE_URL    # SiliconFlow 或 DeepSeek 等
#      QWEATHER_API_KEY / QWEATHER_API_HOST       # 和风天气
#      SYSTEM_PROMPT                              # Agent 系统提示词

# 4. 启动 Agent（多轮交互）
python -m src.agent.react_agent
```

> **注意**：必须用 `python -m src.agent.react_agent` 模块方式启动，
> 不可直接 `python src/agent/react_agent.py`（绝对导入会报 `ModuleNotFoundError`）。

**交互示例**：

```
你: 北京天气怎么样？
（Agent 自动补全"今天"作为默认日期，回答末尾会告知补全信息）

你: 那明天呢？
（基于上下文推断，继续查询北京）

你: exit
```

---

## 评测复现

5 套评测脚本对应论文第 5 章 5 份评测集，全部支持三层缓存与断点续跑：

```bash
# 通路 A 混合检索（60 用例 × 3 档检索器，约 12 秒）
python -m experiments.eval.run_rag_eval

# 通路 A 权重扫描（60 用例 × 8 个权重点，约 12 秒）
python -m experiments.eval.run_rag_weight_sweep

# 通路 B 桥接 4 档消融（71 用例 × 4 档，首次约 25 分钟，缓存后约 7 秒）
python -m experiments.eval.run_bridge_eval --with-llm-baseline

# 意图识别 + 参数补全（35 用例，首次约 11 分钟，缓存后约 7 秒）
python -m experiments.eval.run_intent_eval

# 代码生成 + 沙箱执行 3 档消融（18 用例，首次约 4 分钟，缓存后约 5 秒）
python -m experiments.eval.run_code_eval

# 端到端任务完成率（30 用例 × 2 档 + LLM-as-judge，首次约 60–90 分钟）
python -m experiments.eval.run_e2e_eval
```

每次运行均输出 `experiments/results/<bench>_<时间戳>.{json,md}` 与
`<bench>_latest.md` 镜像，论文表格与图直接引用 `_latest.md`。

---

## 核心评测结果

| 评测集 | 用例数 | 关键指标 |
|---|---:|---|
| 意图识别 | 35 | 端到端 91.4%，地点角色 100% |
| 通路 A 混合检索 | 60 | Top-1 85.0%，MRR 0.908（vector_w=0.9 最优） |
| 通路 B 语义桥接 | 71 | grade_id 准确 100%，引用真实性 100%（vs LLM 25.4%） |
| 代码生成 + 沙箱 | 18 | 数值准确率 88.9%（vs LLM 直算 66.7%） |
| 端到端集成 | 30 | full 86.7% vs ablated 73.3%；决策类 +50 pp |

完整对照表与失败模式分析见 `docs/写作文档/*-论文素材.md`。

---

## 文档索引

| 文档 | 内容 |
|---|---|
| `docs/写作文档/论文.pdf` | 完整毕业论文 |
| `docs/写作文档/论文.tex` | 论文 LaTeX 源（主文件） |
| `docs/写作文档/草稿/` | 各章节 `.tex` 草稿 |
| `docs/写作文档/开发日志.md` | 18 节开发过程记录（架构演进 + 评测实证） |
| `docs/写作文档/答辩PPT-大纲与讲稿.md` | 答辩 PPT 10 页大纲 + 讲稿 |
| `docs/写作文档/答辩问答清单.md` | 答辩可能被追问的问题与应答 |
| `docs/写作文档/*-论文素材.md` | 5 份评测的论文素材（含完整指标与失败模式） |
| `docs/写作文档/figures/` | 论文配图素材 |
| `docs/写作文档/HUSTthesis.bib` | 参考文献 BibTeX 库 |

---

## 注意事项

1. **API 密钥安全**：`src/config/settings.py` 已加入 `.gitignore`，禁止提交。
   建议后续迁移到 `.env` + `os.environ.get()` 读取。
2. **幻觉防控**：涉及数值计算的任务必须通过代码沙箱完成，严禁依赖 LLM 直接出数。
3. **可复现性**：所有评测脚本支持三层缓存与断点续跑，prompt 字面修改自动失效缓存。
4. **数据合规**：使用公开气象数据接口（和风天气 + Open-Meteo），遵守各 API 的频率限制。

---

## 项目仓库

GitHub：<https://github.com/tomtimo0/weather-forecast-agent>（MIT 许可证）

欢迎评审老师与后续研究者基于本项目派生改进。
