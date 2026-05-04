"""混合检索器

将向量召回（语义相似）与 BM25 召回（关键词命中）的分数加权融合，
再按融合分数排序返回 ``RetrievalHit``。
"""

from typing import Dict, List, Optional, Tuple

from src.config.settings import (
    RAG_BM25_WEIGHT,
    RAG_DEFAULT_TOP_K,
    RAG_VECTOR_WEIGHT,
)
from src.rag.knowledge_base import KnowledgeBase, get_knowledge_base
from src.rag.schema import KnowledgeEntry, RetrievalHit


class HybridRetriever:
    """向量 + BM25 融合检索器。"""

    def __init__(
        self,
        kb: Optional[KnowledgeBase] = None,
        vector_weight: float = RAG_VECTOR_WEIGHT,
        bm25_weight: float = RAG_BM25_WEIGHT,
    ):
        self.kb = kb or get_knowledge_base()
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

    def retrieve(
        self,
        query: str,
        top_k: int = RAG_DEFAULT_TOP_K,
        category: Optional[str] = None,
        recall_size: Optional[int] = None,
    ) -> List[RetrievalHit]:
        """执行混合检索。

        Args:
            query: 自然语言查询
            top_k: 最终返回的命中数
            category: 可选类别过滤（term_definition / grading_standard / operation_guideline）
            recall_size: 各路召回数（默认为 top_k * 3，最少 8）

        Returns:
            按融合分数降序的 RetrievalHit 列表
        """
        if not query or not query.strip():
            return []

        recall = recall_size or max(top_k * 3, 8)
        vector_hits = self.kb.vector_search(query, top_k=recall, category=category)
        bm25_hits = self.kb.bm25_search(query, top_k=recall, category=category)

        score_table: Dict[str, Dict[str, float]] = {}
        for entry, score in vector_hits:
            score_table.setdefault(entry.id, {"entry": entry, "vec": 0.0, "bm": 0.0})
            score_table[entry.id]["vec"] = score
        for entry, score in bm25_hits:
            score_table.setdefault(entry.id, {"entry": entry, "vec": 0.0, "bm": 0.0})
            score_table[entry.id]["bm"] = score

        if not score_table:
            return []

        ranked: List[Tuple[KnowledgeEntry, float, float, float]] = []
        for record in score_table.values():
            entry: KnowledgeEntry = record["entry"]
            fused = record["vec"] * self.vector_weight + record["bm"] * self.bm25_weight
            ranked.append((entry, fused, record["vec"], record["bm"]))

        ranked.sort(key=lambda x: x[1], reverse=True)
        ranked = ranked[:top_k]

        return [
            RetrievalHit(
                entry=entry,
                score=round(fused, 4),
                vector_score=round(vec, 4),
                bm25_score=round(bm, 4),
                rank=i + 1,
            )
            for i, (entry, fused, vec, bm) in enumerate(ranked)
        ]


import threading

_default_retriever: Optional[HybridRetriever] = None
_retriever_lock = threading.Lock()


def get_retriever() -> HybridRetriever:
    """获取进程级单例检索器（double-checked locking，避免并发初始化）。"""
    global _default_retriever
    if _default_retriever is not None:
        return _default_retriever
    with _retriever_lock:
        if _default_retriever is None:
            _default_retriever = HybridRetriever()
    return _default_retriever


def format_hits_for_llm(hits: List[RetrievalHit]) -> str:
    """把检索结果格式化为 LLM 易读的引用文本，包含编号、来源、正文与可信度。

    设计点：
    - 每条命中带"编号 + 标题"，便于 Agent 在回答中引用
    - 正文与适用场景一并给出
    - 出处单独成行，引导 Agent 在回答中带上"依据来源"
    - 给出可信度，便于 Agent 区分官方/常识来源
    """
    if not hits:
        return "（未检索到相关条目）"
    lines: List[str] = []
    for hit in hits:
        e = hit.entry
        src = e.source
        src_text = src.org
        if src.doc_title:
            src_text += f"·{src.doc_title}"
        if src.clause:
            src_text += f"（{src.clause}）"
        lines.append(
            "\n".join([
                f"[{hit.rank}] {e.title}（{e.topic} | {e.confidence}，相关度 {hit.score:.2f}）",
                e.content,
                f"出处：{src_text}",
            ])
        )
    return "\n\n".join(lines)


if __name__ == "__main__":
    retriever = get_retriever()
    queries = [
        "24小时降水30毫米属于什么级别？",
        "今天风力7级，能不能进行高空作业？",
        "高温天气户外作业有什么规定？",
        "小雨是什么意思",
    ]
    for q in queries:
        print("=" * 70)
        print(f"查询：{q}")
        hits = retriever.retrieve(q, top_k=3)
        print(format_hits_for_llm(hits))
        print()
