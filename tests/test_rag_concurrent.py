"""并发触发 RAG 单例初始化的冒烟测试。

复现修复前的 bug：LangGraph 并行调度 bridge_weather_data + search_knowledge
两个工具时，会同时首次访问 RAG 单例，触发 ChromaDB 1.x PersistentClient 的
RustBindingsAPI 'bindings' AttributeError。修复后所有并发调用应正常返回。
"""
from __future__ import annotations

import threading

from src.tools.bridge_tool import bridge_weather_data
from src.tools.knowledge_tool import search_knowledge


def main() -> None:
    results: dict[str, str] = {}
    errors: dict[str, BaseException] = {}

    def run_bridge() -> None:
        try:
            results["bridge"] = bridge_weather_data.invoke(
                {"data_json": '{"precip": "35mm"}', "scene": "出行"}
            )
        except BaseException as exc:  # noqa: BLE001
            errors["bridge"] = exc

    def run_search() -> None:
        try:
            results["search"] = search_knowledge.invoke(
                {"query": "中雨 降水量等级标准", "category": "grading_standard"}
            )
        except BaseException as exc:  # noqa: BLE001
            errors["search"] = exc

    t1 = threading.Thread(target=run_bridge)
    t2 = threading.Thread(target=run_search)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    if errors:
        for name, exc in errors.items():
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
        raise SystemExit(1)

    print("=== bridge_weather_data 输出（前 200 字）===")
    print(results["bridge"][:200])
    print()
    print("=== search_knowledge 输出（前 200 字）===")
    print(results["search"][:200])
    print()
    print("OK: 并发调用未触发 ChromaDB 初始化崩溃")


if __name__ == "__main__":
    main()
