"""轻量代码执行器：受限沙箱 + 超时 + 异常捕获

设计目标
--------
为 Agent 提供一个**仅可信代码用途**的轻量执行环境，专门承载下游
``code_generator`` 生成的"统计分析函数"。它**不是**通用安全沙箱，
不打算抵御主动恶意代码，仅用于：

1. 拒绝常见的破坏性内置（``open`` / ``eval`` / ``exec`` / ``__import__``）
2. 限制可见模块到一组只读数学库（``math`` / ``statistics``）
3. 提供墙钟超时（默认 5 秒）防止意外死循环
4. 把代码异常转化为结构化错误，避免污染主流程

接口约定
--------
传入的 ``code`` 必须定义一个顶层函数 ``compute(data) -> Any``：

```python
def compute(data):
    daily = data["daily"]
    return statistics.mean(d["tempMax"] for d in daily)
```

执行器：

- 在受限 globals 中 ``exec`` 一遍源码（拿到 ``compute`` 函数对象）
- 把 ``data`` 传进去调用，捕获返回值
- 整个调用包在 ``ThreadPoolExecutor.submit(...).result(timeout)`` 里
  实现墙钟超时（Windows 兼容，无需 ``signal.SIGALRM``）

设计取舍
--------
真正的安全沙箱（RestrictedPython / Pyodide / Docker 隔离）超出本毕设
研究范围；本模块仅作为论文 "代码生成 + 执行" 工程方案的最小可用原型，
重点是为下游评测脚本（``run_code_eval.py``）提供可重复、可测量的
执行通道。
"""

from __future__ import annotations

import builtins as _builtins_mod
import math
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# 显式白名单：仅暴露这些 builtins 给受限作用域
_ALLOWED_BUILTINS = {
    name: getattr(_builtins_mod, name) for name in (
        # 数值与逻辑
        "abs", "all", "any", "bool", "complex", "divmod", "float", "int",
        "max", "min", "pow", "round", "sum",
        # 集合与迭代
        "dict", "list", "tuple", "set", "frozenset", "range",
        "len", "sorted", "reversed", "enumerate", "filter", "map", "zip",
        "iter", "next",
        # 类型与字符串
        "str", "repr", "isinstance", "type",
        # 常量
        "True", "False", "None",
        # 异常与错误（允许代码内部 try/except）
        "Exception", "ValueError", "TypeError", "KeyError", "IndexError",
        "ZeroDivisionError", "ArithmeticError", "StopIteration",
    ) if hasattr(_builtins_mod, name)
}


# 显式白名单：仅暴露这些只读模块给受限作用域
_ALLOWED_MODULES = {
    "math": math,
    "statistics": statistics,
}


# 显式黑名单：即使白名单不小心放行也强制屏蔽
_FORBIDDEN_NAMES = frozenset({
    "open", "eval", "exec", "compile", "__import__", "input",
    "breakpoint", "exit", "quit", "globals", "locals", "vars",
    "memoryview", "object", "super",
})


@dataclass
class ExecutionResult:
    """代码执行结果。

    字段
    ----
    success: 是否执行到位并拿到返回值
    value: ``compute(data)`` 的返回值（任意 picklable 类型）
    error: 失败原因（解析错误 / 运行时异常 / 超时 / 缺函数）
    elapsed_ms: 实际墙钟耗时
    code: 原始源码（便于调试落盘）
    """

    success: bool
    value: Any = None
    error: Optional[str] = None
    elapsed_ms: float = 0.0
    code: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


def _build_restricted_globals() -> Dict[str, Any]:
    """构造受限 globals：仅含白名单 builtins + 白名单模块。"""
    safe_builtins = {
        k: v for k, v in _ALLOWED_BUILTINS.items() if k not in _FORBIDDEN_NAMES
    }
    return {
        "__builtins__": safe_builtins,
        **_ALLOWED_MODULES,
    }


def execute_code(
    code: str,
    data: Any,
    timeout: float = 5.0,
) -> ExecutionResult:
    """在受限 globals 中执行 ``code``，调用其中的 ``compute(data)`` 函数。

    Args:
        code: 必须包含顶层 ``def compute(data): ...`` 的 Python 源码
        data: 透传给 ``compute`` 的输入（字典 / 列表 / 标量都可以）
        timeout: 墙钟超时秒数；超过则返回 ``error="timeout"``

    Returns:
        ``ExecutionResult``。无论何种失败模式都不会抛异常，
        统一在返回值里通过 ``success`` 与 ``error`` 字段反馈。
    """
    started = time.perf_counter()
    namespace: Dict[str, Any] = {}
    safe_globals = _build_restricted_globals()

    # ---- 第一步：解析并加载代码 ----
    try:
        compiled = compile(code, "<llm_generated>", "exec")
    except SyntaxError as exc:
        return ExecutionResult(
            success=False,
            error=f"语法错误：{exc}",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            code=code,
        )

    try:
        exec(compiled, safe_globals, namespace)  # noqa: S102 受限 globals
    except Exception as exc:  # noqa: BLE001
        return ExecutionResult(
            success=False,
            error=f"加载阶段异常：{type(exc).__name__}: {exc}",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            code=code,
        )

    compute_fn = namespace.get("compute")
    if not callable(compute_fn):
        return ExecutionResult(
            success=False,
            error="代码中未定义 compute(data) 函数",
            elapsed_ms=(time.perf_counter() - started) * 1000,
            code=code,
        )

    # ---- 第二步：在 daemon 线程里调用，实现墙钟超时 ----
    # 注意：Python 没有可靠的线程强制终止机制，因此死循环代码并不会真的被
    # "杀掉"——它会作为 daemon 线程继续在后台跑，直到主进程退出时被运行时
    # 强行回收。这是受限沙箱原型的已知局限，但满足毕设场景下"不阻塞主流程
    # 的评测推进"这一最低要求。
    container: Dict[str, Any] = {}

    def _runner() -> None:
        try:
            container["value"] = compute_fn(data)
            container["status"] = "ok"
        except Exception as exc:  # noqa: BLE001
            container["status"] = "error"
            container["error"] = f"运行时异常：{type(exc).__name__}: {exc}"

    worker = threading.Thread(target=_runner, daemon=True)
    worker.start()
    worker.join(timeout=timeout)

    elapsed_ms = (time.perf_counter() - started) * 1000

    if worker.is_alive():
        return ExecutionResult(
            success=False,
            error=f"超时（>{timeout}s）",
            elapsed_ms=elapsed_ms,
            code=code,
            extra={"worker_still_alive": True},
        )

    if container.get("status") == "ok":
        return ExecutionResult(
            success=True,
            value=container.get("value"),
            elapsed_ms=elapsed_ms,
            code=code,
        )

    return ExecutionResult(
        success=False,
        error=container.get("error", "未知错误（线程结束但无返回）"),
        elapsed_ms=elapsed_ms,
        code=code,
    )


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    samples = [
        (
            "正常算例（平均最高温）",
            """
def compute(data):
    daily = data["daily"]
    return statistics.mean(d["tempMax"] for d in daily)
""",
            {"daily": [{"tempMax": 18.0}, {"tempMax": 22.0}, {"tempMax": 26.0}]},
        ),
        (
            "故意不允许的 open()",
            """
def compute(data):
    return open("a.txt").read()
""",
            {},
        ),
        (
            "故意 import os",
            """
def compute(data):
    import os
    return os.listdir(".")
""",
            {},
        ),
        (
            "故意死循环（1.5s 后超时）",
            """
def compute(data):
    while True:
        pass
""",
            {},
        ),
        (
            "compute 缺失",
            """
def helper():
    return 1
""",
            {},
        ),
        (
            "运行时异常（除零）",
            """
def compute(data):
    return 1 / 0
""",
            {},
        ),
    ]
    for title, code, data in samples:
        print(f"--- {title} ---")
        result = execute_code(code, data, timeout=1.5)
        print(
            f"success={result.success}  value={result.value!r}  "
            f"error={result.error}  elapsed={result.elapsed_ms:.1f}ms"
        )
