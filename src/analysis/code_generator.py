"""LLM 代码生成器：把"统计分析自然语言查询 + 数据"转成可执行 Python 函数

公平性原则
----------
- prompt 不告诉 LLM 答案，只告诉它「数据形状 + 任务目标 + 函数签名约定」
- LLM 必须输出一个完整、可独立执行的 ``compute(data)`` 函数
- 禁止 ``import``（除受限白名单 ``math`` / ``statistics`` 外）
- 禁止 ``print`` / ``open`` / ``eval`` / ``exec`` / 文件 I/O / 网络

输出 schema 与 ``code_executor.execute_code`` 配套：

```python
def compute(data):
    daily = data["daily"]
    return statistics.mean(d["tempMax"] for d in daily)
```

调用流程
--------
``generate_code(query, data)`` → ``CodeGenResult`` →
``code_executor.execute_code(result.code, data)`` → ``ExecutionResult``
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


CODE_GEN_PROMPT_VERSION = "v1"


CODE_GEN_SYSTEM_PROMPT = """你是一个气象数据分析专家。
你的任务是根据用户的自然语言查询和给定的数据样例，生成一段 Python 代码用于计算答案。

## 函数签名约定（强制）
你必须生成一个名为 ``compute`` 的顶层函数，签名为 ``compute(data) -> Any``：

```python
def compute(data):
    # 你的实现
    return result   # 返回数值/列表/字典等可序列化对象
```

## 受限运行环境
- **禁止 import 任何模块**（math 与 statistics 已自动注入到全局命名空间，可以直接使用）
- **禁止使用** open / eval / exec / compile / __import__ / input / print / 任何文件或网络 I/O
- **禁止使用** os / sys / subprocess / pathlib / requests 等模块
- 允许的 builtins：abs/all/any/sum/max/min/round/sorted/zip/enumerate/range/len/dict/list/str/int/float/bool/...

## 编写规范
1. ``compute`` 函数应是**纯函数**：仅依赖输入 data 与受限全局命名空间，不读写任何外部状态
2. 数据访问使用 ``data["key"]`` 或 ``data.get("key", default)``
3. 涉及统计运算时优先使用 ``statistics.mean`` / ``statistics.median`` / ``statistics.stdev`` 等
4. 涉及四舍五入时使用 ``round(value, n)`` 保持一致精度
5. 当用户问的是"哪一天"或"哪个城市"时，应返回对应的标识符（日期串/城市名），而非数值索引

## 输出要求
- ``code`` 字段：完整可执行的 Python 源码，必须包含 ``def compute(data):`` 顶层定义
- ``reasoning`` 字段：1-2 句简短解释你的算法思路，便于调试

## 严禁
- 严禁在 code 中调用 input() 或读取任何外部文件
- 严禁在 code 中产生网络请求
- 严禁返回 None；如确无法计算，请抛 ValueError 并附简短理由
"""


class CodeGenResult(BaseModel):
    """LLM 生成的代码及解释。"""

    code: str = Field(
        description="完整可执行的 Python 源码，必须含顶层 def compute(data):"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="1-2 句解释算法思路，便于调试与论文展示",
    )


_codegen_singleton = None


def _get_codegen_llm():
    """惰性创建 LLM 客户端单例（带 timeout / max_retries 加固）。"""
    global _codegen_singleton
    if _codegen_singleton is None:
        llm = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            temperature=0,
            timeout=60,
            max_retries=2,
        )
        _codegen_singleton = llm.with_structured_output(
            CodeGenResult, method="function_calling"
        )
    return _codegen_singleton


def _truncate_data_for_prompt(data: Any, max_chars: int = 1500) -> str:
    """把 data 序列化成 JSON 字符串供 prompt 展示，超长时截断尾部。"""
    text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [已截断，原始 {len(text)} 字符]"


def generate_code(
    query: str,
    data: Any,
    max_retries: int = 1,
) -> CodeGenResult:
    """让 LLM 根据 query 与 data 生成 ``compute(data)`` 函数。

    Args:
        query: 用户自然语言查询，如"过去 7 天武汉最高温的平均值是多少？"
        data: 完整数据 dict，会序列化后注入 prompt 作为 schema + 样例
        max_retries: 结构化输出失败时的额外重试次数

    Returns:
        ``CodeGenResult``。失败时 ``code`` 为空字符串、``reasoning`` 含失败原因。
    """
    structured = _get_codegen_llm()
    user_msg = (
        f"## 用户查询\n{query}\n\n"
        f"## 完整数据（compute(data) 调用时会原样传入）\n"
        f"```json\n{_truncate_data_for_prompt(data)}\n```\n\n"
        f"请生成 compute(data) 函数。"
    )
    last_error: str = ""
    for _attempt in range(max_retries + 1):
        try:
            raw = structured.invoke([
                {"role": "system", "content": CODE_GEN_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ])
            if isinstance(raw, CodeGenResult):
                return raw
            last_error = "LLM 未触发结构化输出"
        except Exception as exc:  # noqa: BLE001
            last_error = f"调用异常：{exc}"
    return CodeGenResult(code="", reasoning=f"代码生成失败：{last_error}")


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from src.tools.code_executor import execute_code

    sample_data = {
        "city": "武汉",
        "daily": [
            {"date": "2025-04-01", "tempMax": 18.5, "tempMin": 8.2, "precip": 0.0},
            {"date": "2025-04-02", "tempMax": 20.3, "tempMin": 9.1, "precip": 1.2},
            {"date": "2025-04-03", "tempMax": 22.7, "tempMin": 11.5, "precip": 5.4},
            {"date": "2025-04-04", "tempMax": 19.0, "tempMin": 10.0, "precip": 12.8},
            {"date": "2025-04-05", "tempMax": 16.5, "tempMin": 7.3, "precip": 0.3},
            {"date": "2025-04-06", "tempMax": 21.4, "tempMin": 9.8, "precip": 0.0},
            {"date": "2025-04-07", "tempMax": 24.1, "tempMin": 12.6, "precip": 0.0},
        ],
    }
    queries = [
        "过去 7 天武汉每天最高温的平均值是多少？",
        "过去 7 天累计降水量是多少？",
        "过去 7 天里温差最大的是哪一天？温差是多少？",
    ]
    for q in queries:
        print(f"\n===== {q} =====")
        gen = generate_code(q, sample_data)
        print("--- code ---")
        print(gen.code or "(空)")
        print(f"--- reasoning: {gen.reasoning} ---")
        if gen.code:
            run = execute_code(gen.code, sample_data, timeout=5.0)
            print(
                f"execute: success={run.success}  value={run.value!r}  "
                f"error={run.error}  elapsed={run.elapsed_ms:.1f}ms"
            )
