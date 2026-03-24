# 基于AI智能体的气象预报数据检索与分析

> 毕业设计项目 · 2025-2026

## 一、项目概述

本项目旨在构建一个**基于大语言模型（LLM）AI智能体**的气象预报数据检索与分析系统。系统采用 **ReAct（Reasoning + Acting）** 范式，将自然语言气象查询任务自动转化为结构化 API 调用，完成异构气象数据的智能检索、统计分析与决策报告生成。

### 核心研究问题

| 编号 | 问题 | 对应章节 |
|------|------|----------|
| **Q1** | 气象任务指令解析——如何将用户自然语言查询精准映射为结构化检索参数 | 第3章 |
| **Q2** | 气象数据的异构特征分析——如何统一处理多源、多模态、多时空尺度的气象数据 | 第4章 |
| **Q3** | LLM 数值计算与逻辑推理的幻觉问题——如何保证统计分析结果的确定性与可靠性 | 第4章 |

---

## 二、系统架构

┌─────────────────────────────────────────────────────────────┐
│                    用户自然语言输入                           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              气象 Agent（ReAct 单智能体）                     │
│  ┌───────────┐  ┌───────────────┐  ┌──────────────────┐    │
│  │  思维链    │→│  意图识别与    │→│  工具调用决策     │    │
│  │ (CoT)     │  │  指令解析      │  │  (Tool Selection)│    │
│  └───────────┘  └───────────────┘  └────────┬─────────┘    │
│                                              │              │
│  ┌───────────────────────────────────────────┼────────┐     │
│  │            RAG 领域知识库                   │        │     │
│  │  (气象术语/业务规则/Prompt模板)             │        │     │
│  └───────────────────────────────────────────┼────────┘     │
└──────────────────────────────────────────────┼──────────────┘
                                               ▼
                    ┌──────────────────────────────────────┐
                    │           工具层 (Tools)              │
                    │  ┌──────────┐  ┌──────────────────┐  │
                    │  │气象API   │  │代码执行沙箱      │  │
                    │  │检索工具  │  │(统计分析)        │  │
                    │  └──────────┘  └──────────────────┘  │
                    │  ┌──────────┐  ┌──────────────────┐  │
                    │  │数据预处理│  │语义桥接 &        │  │
                    │  │工具      │  │报告生成模块      │  │
                    │  └──────────┘  └──────────────────┘  │
                    └──────────────────────────────────────┘
                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  输出：气象决策分析报告                       │
└─────────────────────────────────────────────────────────────┘

---

## 三、技术路线与关键技术

### 3.1 基于 ReAct 范式的单智能体思维链模型（第2章）

- **核心框架**：采用 ReAct（Reasoning + Acting）范式，交替执行"推理-行动-观察"循环
- **思维链 (Chain-of-Thought)**：引导 LLM 逐步分解复杂气象任务
- **关键参考**：Wei et al. (2022) CoT; Yao et al. (2023) ReAct; Yao et al. (2024) Tree of Thoughts

### 3.2 基于工具学习的异构气象数据智能检索（第3章，解决 Q1）

- **气象 API 封装**：将各类气象数据接口（实况、预报、历史数据等）统一封装为工具描述（Tool Description）
- **意图识别与指令化**：自然语言 → 结构化检索参数的映射
- **缺失参数推理与动态补全**：利用上下文信息推断并补全未明确指定的检索参数（如默认地点、时间范围等）
- **关键参考**：Schick et al. (2023) Toolformer; Patil et al. (2023) Gorilla; MCP Specification (2024)

### 3.3 融合语义桥接机制的气象数据统计分析（第4章，解决 Q2 & Q3）

- **代码生成驱动的确定性分析**：将统计计算任务转化为可执行代码（Python），避免 LLM 直接数值计算产生幻觉
- **"数据-文本"语义桥接算法**：建立气象数值特征到自然语言语义描述的映射表（如温度区间→体感描述）
- **自适应报告生成**：根据任务类型和数据特征自动选择报告模板并生成结构化分析报告
- **关键参考**：Hong et al. (2024) Data Interpreter; Gruver et al. (2024) LLM Zero-Shot Time Series

> **⚠️ 关于"语义桥接"的核心定义**
>
> 本项目中的**语义桥接（Semantic Bridge）** 是指：在气象 API 返回原始数据（JSON、表格等）**送入 LLM 之前**，先通过确定性脚本（非 LLM）将原始数值数据转化为自然语言语义描述的预处理过程。
>
> **为什么要这样做？** LLM 直接处理大量原始数值表格时，容易产生数值幻觉（编造数据、计算错误、忽略关键数值等）。语义桥接通过在 LLM 介入之前就用规则脚本完成"数值→语义"的确定性转换，使 LLM 只需要基于已经转化好的语义描述来组织语言和生成报告，从而大幅降低幻觉率。
>
> **处理流程：**
> ```
> 气象API返回原始数据 (JSON/表格)
>        │
>        ▼
> 语义桥接脚本（确定性规则，非LLM）
>   ├─ 温度 12.3°C → "凉爽，建议穿外套"
>   ├─ 风力 7级 → "疾风，不宜户外活动"
>   └─ 降水概率 85% → "大概率有雨，建议携带雨具"
>        │
>        ▼
> 转化后的语义描述文本（而非原始数值表格）
>        │
>        ▼
> 输入给 LLM → 组织语言，生成决策分析报告
> ```
>
> **关键原则：** 语义桥接是**确定性的预处理步骤**，由脚本和映射规则完成，不依赖 LLM，确保转换结果 100% 可靠。LLM 的职责是基于这些可靠的语义素材进行自然语言组织和报告生成，而不是直接解读原始数值。

### 3.4 基于 RAG 的领域知识注入（贯穿全系统）

- **知识库构建**：气象专业术语、业务规则、地理编码映射等
- **Prompt 工程优化**：结合检索增强生成（RAG）动态注入领域知识到 Prompt 中
- **关键参考**：Lewis et al. (2020) RAG; Gao et al. (2023) RAG Survey

---

## 四、技术栈（建议）

| 类别 | 技术选型 | 说明 |
|------|----------|------|
| **LLM 后端** | OpenAI GPT-4 / 通义千问 / DeepSeek | 主推理引擎，支持 Function Calling |
| **Agent 框架** | LangChain / LlamaIndex | ReAct Agent 构建、工具编排、记忆管理 |
| **代码执行** | Python 沙箱（subprocess / Docker） | 统计分析代码的安全执行环境 |
| **RAG 组件** | FAISS / ChromaDB + Embedding Model | 领域知识向量检索 |
| **气象数据源** | 和风天气 API / OpenWeatherMap / CMA 开放数据 | 多源异构气象数据接入 |
| **前端（可选）** | Streamlit / Gradio | 交互式演示界面 |
| **开发语言** | Python 3.10+ | 主开发语言 |

---

## 五、项目目录规划

```
d:\毕设\
├── README.md                          # 本文件 - 项目指南
├── docs/                              # 论文与文档
│   ├── thesis/                        # 毕业论文相关文档
│   └── references/                    # 参考文献 PDF
├── src/                               # 源代码根目录
│   ├── agent/                         # Agent 核心模块
│   │   ├── react_agent.py             # ReAct Agent 主控逻辑
│   │   ├── prompts/                   # Prompt 模板
│   │   │   ├── system_prompt.py       # 系统级 Prompt
│   │   │   ├── task_prompts.py        # 任务 Prompt 模板
│   │   │   └── few_shot_examples.py   # Few-shot 示例
│   │   └── memory.py                  # 对话记忆与上下文管理
│   ├── tools/                         # 工具模块（对应第3章）
│   │   ├── weather_api.py             # 气象 API 封装
│   │   ├── data_retrieval.py          # 数据检索工具
│   │   ├── code_executor.py           # 代码执行沙箱
│   │   └── tool_registry.py           # 工具注册与描述管理
│   ├── rag/                           # RAG 模块（对应第2.3节）
│   │   ├── knowledge_base.py          # 领域知识库管理
│   │   ├── embedding.py               # 向量嵌入
│   │   └── retriever.py               # 知识检索器
│   ├── analysis/                      # 数据分析模块（对应第4章）
│   │   ├── code_generator.py          # 分析代码自动生成
│   │   ├── semantic_bridge.py         # 数据-文本语义桥接
│   │   └── report_generator.py        # 决策报告生成
│   ├── config/                        # 配置文件
│   │   ├── settings.py                # 全局配置
│   │   └── api_keys.py                # API 密钥（.gitignore）
│   └── utils/                         # 公共工具函数
│       ├── logger.py                  # 日志工具
│       └── data_utils.py              # 数据处理工具
├── data/                              # 数据目录
│   ├── knowledge/                     # RAG 知识库原始数据
│   │   ├── weather_terms.json         # 气象术语库
│   │   ├── geo_mapping.json           # 地理编码映射
│   │   └── business_rules.json        # 气象业务规则
│   ├── semantic_mapping/              # 语义桥接映射表
│   │   └── value_to_text.json         # 数值-语义特征映射
│   └── test_cases/                    # 测试用例与数据集
│       ├── benchmark.json             # 评测数据集
│       └── scenarios/                 # 典型场景用例
├── experiments/                       # 实验相关（对应第5章）
│   ├── eval/                          # 评测脚本
│   │   ├── metrics.py                 # 评测指标定义
│   │   └── run_eval.py               # 评测运行脚本
│   ├── ablation/                      # 消融实验
│   └── results/                       # 实验结果记录
├── notebooks/                         # Jupyter 探索性分析
├── tests/                             # 单元测试
├── requirements.txt                   # Python 依赖
└── .gitignore                         # Git 忽略文件
```

---

## 六、研究实施路线图

### 阶段一：基础设施搭建（预计 2 周）

- [ ] 初始化项目仓库，搭建目录结构
- [ ] 配置开发环境（Python 虚拟环境、依赖安装）
- [ ] 调研并选定气象数据 API，完成 API 账号注册与测试
- [ ] 搭建基础 LLM 调用链路（选定模型、测试 API 连通性）
- [ ] 确定 Agent 框架选型（LangChain vs 自研），完成技术选型文档

**里程碑**：能够通过代码调用 LLM 和气象 API，获取基本气象数据

### 阶段二：Agent 核心 + 工具检索（预计 3-4 周，对应第2-3章）

- [ ] 实现 ReAct Agent 主控循环（Thought → Action → Observation）
- [ ] 设计并实现气象 API 工具封装（Tool Description Schema）
- [ ] 实现意图识别模块：自然语言 → 结构化检索参数
- [ ] 实现缺失参数的上下文推理与动态补全逻辑
- [ ] 构建 RAG 知识库（气象术语、地理编码、业务规则）
- [ ] 设计 System Prompt 与 Few-shot 示例模板
- [ ] 集成 RAG 检索到 Agent Prompt 中

**里程碑**：Agent 能够理解自然语言气象查询，自动调用正确 API 并返回原始数据

### 阶段三：统计分析与语义桥接（预计 3-4 周，对应第4章）

- [ ] 实现代码生成模块：根据分析需求自动生成 Python 统计分析代码
- [ ] 实现代码执行沙箱，确保安全执行并捕获结果
- [ ] 构建"数值-语义"特征映射表（温度区间、风力等级、降水量级等）
- [ ] 实现语义桥接算法：将数值分析结果映射为自然语言描述
- [ ] 实现自适应报告生成模块（多场景模板 + 动态内容填充）
- [ ] 端到端联调：查询 → 检索 → 分析 → 报告生成全流程

**里程碑**：系统能够完成"从自然语言提问到结构化分析报告输出"的完整闭环

### 阶段四：实验评估与论文撰写（预计 3-4 周，对应第5章）

- [ ] 构建评测数据集：覆盖多种典型气象查询场景
- [ ] 定义评测指标：
  - 意图识别准确率（Q1 评估）
  - 检索参数完整性与正确率（Q1 评估）
  - 统计分析结果准确性（Q2/Q3 评估）
  - 报告生成质量（BLEU / ROUGE / 人工评分）
  - 端到端任务完成率
- [ ] 执行消融实验：
  - 有/无 RAG 知识注入对比
  - 有/无语义桥接对比
  - 有/无代码生成（直接 LLM 计算 vs 代码执行）对比
  - 不同 LLM 后端对比（可选）
- [ ] 整理实验结果，绘制图表
- [ ] 撰写论文各章节

**里程碑**：完成全部实验，论文初稿完成

---

## 七、关键设计要点备忘

### 7.1 ReAct Agent 循环伪代码

```python
def react_loop(query: str, max_steps: int = 10) -> str:
    """ReAct 主循环：交替执行推理与行动"""
    context = initialize_context(query)

    for step in range(max_steps):
        # Thought: LLM 推理当前应执行什么操作
        thought = llm.reason(context)

        # Action: 根据推理结果选择并调用工具
        action, action_input = parse_action(thought)
        if action == "FINISH":
            return thought.final_answer

        # Observation: 获取工具执行结果
        observation = execute_tool(action, action_input)

        # 将本轮结果追加到上下文
        context.append(thought, action, observation)

    return generate_fallback_response(context)
```

### 7.2 气象 API 工具描述模板

```json
{
  "name": "get_weather_forecast",
  "description": "获取指定城市未来N天的天气预报数据，包括温度、湿度、风力、降水概率等",
  "parameters": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string",
        "description": "城市名称或城市编码"
      },
      "days": {
        "type": "integer",
        "description": "预报天数（1-15）",
        "default": 3
      },
      "metrics": {
        "type": "array",
        "items": { "type": "string" },
        "description": "需要的气象要素列表，如 ['temperature', 'humidity', 'wind']"
      }
    },
    "required": ["city"]
  }
}
```

### 7.3 语义桥接映射示例

```json
{
  "temperature": {
    "ranges": [
      { "min": -40, "max": -10, "label": "极寒", "suggestion": "极端低温，请做好全面防寒措施" },
      { "min": -10, "max": 0,   "label": "严寒", "suggestion": "注意防寒保暖，减少户外活动" },
      { "min": 0,   "max": 10,  "label": "寒冷", "suggestion": "需要穿着厚实冬装" },
      { "min": 10,  "max": 20,  "label": "凉爽", "suggestion": "建议穿着外套或薄毛衣" },
      { "min": 20,  "max": 28,  "label": "舒适", "suggestion": "适宜户外活动" },
      { "min": 28,  "max": 35,  "label": "炎热", "suggestion": "注意防暑降温，及时补充水分" },
      { "min": 35,  "max": 50,  "label": "酷热", "suggestion": "高温预警，尽量避免户外活动" }
    ]
  },
  "wind_scale": {
    "ranges": [
      { "min": 0, "max": 2,  "label": "微风",   "impact": "对日常活动无影响" },
      { "min": 3, "max": 4,  "label": "和风",   "impact": "适宜户外活动" },
      { "min": 5, "max": 6,  "label": "清劲风", "impact": "户外活动需注意" },
      { "min": 7, "max": 8,  "label": "疾风",   "impact": "不宜进行户外活动" },
      { "min": 9, "max": 12, "label": "烈风",   "impact": "存在安全隐患，应留在室内" }
    ]
  }
}
```

---

## 八、核心参考文献速查

| 主题 | 关键文献 | 用途 |
|------|----------|------|
| Agent 综述 | Xi et al. (2023) LLM Agent Survey | 理论框架，Agent 分类与能力边界 |
| ReAct 范式 | Yao et al. (2023) ReAct | Agent 核心架构设计 |
| 思维链推理 | Wei et al. (2022) CoT | Prompt 设计策略 |
| 思维树 | Yao et al. (2024) Tree of Thoughts | 复杂推理任务拓展 |
| 工具学习 | Schick et al. (2023) Toolformer | 工具调用机制设计 |
| API 调用 | Patil et al. (2023) Gorilla | LLM 连接大规模 API |
| MCP 协议 | MCP Specification (2024) | 工具协议标准参考 |
| RAG 基础 | Lewis et al. (2020) RAG | 知识检索增强生成 |
| RAG 综述 | Gao et al. (2023) RAG Survey | RAG 最新进展与最佳实践 |
| 数据解释器 | Hong et al. (2024) Data Interpreter | 代码生成分析范式参考 |
| 时序预测 | Gruver et al. (2024) LLM Zero-Shot TS | LLM 处理时间序列的能力与局限 |
| 气象 Agent | Kim et al. (2025) CLIMATEAGENT | 气象多智能体编排参考 |
| 气象 AI 应用 | 李特等 (2025); 代刊等 (2025) | 国内气象 AI 应用现状 |
| Agent 框架 | LangChain (2022); AutoGen (2023) | 工程实现框架参考 |

---

## 九、注意事项

1. **API 密钥安全**：所有 API 密钥存放于 `src/config/api_keys.py`，并添加到 `.gitignore`，禁止提交到版本库
2. **幻觉防控**：涉及数值计算的任务**必须**通过代码执行完成，严禁依赖 LLM 直接输出数值结果
3. **可复现性**：所有实验需记录完整的配置参数（模型版本、温度参数、Prompt 版本等），便于消融实验对比
4. **数据合规**：使用公开气象数据接口，注意遵守各 API 的使用条款和频率限制
5. **版本管理**：建议尽早初始化 Git 仓库，按功能模块分支开发，保持提交粒度适中

---

## 十、快速开始

```bash
# 1. 克隆/初始化项目
cd d:\毕设
git init

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置 API 密钥
cp src/config/api_keys.example.py src/config/api_keys.py
# 编辑 api_keys.py 填入实际密钥

# 5. 运行 Agent（开发完成后）
python src/agent/react_agent.py
```

---

*本 README 将随项目进展持续更新。*
