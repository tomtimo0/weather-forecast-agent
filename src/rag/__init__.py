"""RAG (Retrieval-Augmented Generation) 模块

提供气象领域知识的检索能力，支持术语解释、分级标准、作业规范三类知识。
"""

from src.rag.schema import KnowledgeEntry, RetrievalHit, KnowledgeCategory
from src.rag.knowledge_base import KnowledgeBase
from src.rag.retriever import HybridRetriever, get_retriever

__all__ = [
    "KnowledgeEntry",
    "RetrievalHit",
    "KnowledgeCategory",
    "KnowledgeBase",
    "HybridRetriever",
    "get_retriever",
]
