"""知识库检索工具

把 RAG 检索能力封装为 LangChain Tool，供 Agent 在需要"术语解释 / 分级标准 / 作业规范"
等领域知识依据时主动调用。
"""

from typing import Optional

from langchain.tools import tool

from src.rag.retriever import format_hits_for_llm, get_retriever


@tool
def search_knowledge(query: str, category: Optional[str] = None, top_k: int = 4) -> str:
    """从气象领域知识库检索权威定义、分级标准与作业规范，返回带出处的依据文本。

    应当在以下情形主动调用本工具：
    - 用户问"什么是 X"、"X 是什么意思"等术语定义类问题
    - 用户问"X 毫米 / X 级 / X 度 属于什么级别"等分级阈值问题
    - 用户问"是否适合 X（高空作业、跑步、洗车、农业播种等）"且需要对照规范
    - 输出穿衣 / 出行 / 安全建议时，需要引用权威条款作依据

    Args:
        query: 自然语言查询，越具体越好。例如："24小时降水30毫米是什么级别"、
               "高空作业风力达到几级要停止"
        category: 可选过滤类别。取值之一：
                  - "term_definition"：术语定义（毛毛雨、雷暴、台风等）
                  - "grading_standard"：分级标准（降水/风力/能见度/温度等）
                  - "operation_guideline"：作业与出行规范（高空作业/户外/驾驶等）
                  传 None 表示在所有类别中检索。
        top_k: 返回的命中数，默认 4，建议范围 1–6。

    Returns:
        多条按相关度降序排列的知识条目文本，每条包含：编号、标题、正文、出处、可信度。
        Agent 在回答时应优先采用 confidence=official 的条目作为依据，并在回答中引用出处。
    """
    retriever = get_retriever()
    hits = retriever.retrieve(query, top_k=top_k, category=category)
    if not hits:
        return "（知识库中未检索到与该查询相关的条目，请基于工具返回的实测/预报数据自行作答，并在回答中说明「未找到权威依据」。）"
    return format_hits_for_llm(hits)


if __name__ == "__main__":
    print(search_knowledge.invoke({"query": "24小时降水40毫米是什么级别？"}))
    print()
    print(search_knowledge.invoke({"query": "高空作业风力多少级要停止", "category": "operation_guideline"}))
