"""知识库加载与索引管理

职责：
- 从 ``data/knowledge/*.jsonl`` 加载 ``KnowledgeEntry`` 列表
- 维护 ChromaDB 向量索引（持久化到磁盘，避免每次重新嵌入）
- 维护内存 BM25 词法索引
- 提供向量检索 / BM25 检索的原子接口（融合在 retriever.py 完成）
"""

import json
import os
import re
from typing import Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from rank_bm25 import BM25Okapi

from src.config.settings import (
    CHROMA_PERSIST_DIR,
    KNOWLEDGE_DATA_DIR,
    RAG_COLLECTION_NAME,
)
from src.rag.embedding import EmbeddingClient, get_embedding_client
from src.rag.schema import KnowledgeEntry


def _tokenize_zh(text: str) -> List[str]:
    """简易中英混合分词：按非字母数字字符切分，再补充逐字汉字 token。

    BM25 在中文上分词粒度对结果影响较大，这里采用"词+字"双粒度策略，
    让"小雨"、"24小时"等连续词与单字"雨"都能被命中。
    """
    if not text:
        return []
    text = text.lower()
    word_tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text)
    char_tokens: List[str] = []
    for token in word_tokens:
        if re.match(r"^[\u4e00-\u9fff]+$", token):
            char_tokens.extend(list(token))
    return word_tokens + char_tokens


class KnowledgeBase:
    """加载知识条目并维护两套索引（向量 + BM25）。"""

    def __init__(
        self,
        data_dir: str = KNOWLEDGE_DATA_DIR,
        persist_dir: str = CHROMA_PERSIST_DIR,
        collection_name: str = RAG_COLLECTION_NAME,
        embedding_client: Optional[EmbeddingClient] = None,
    ):
        self.data_dir = data_dir
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_client = embedding_client or get_embedding_client()

        self.entries: List[KnowledgeEntry] = []
        self._entry_index: Dict[str, KnowledgeEntry] = {}
        self._bm25: Optional[BM25Okapi] = None
        self._bm25_doc_ids: List[str] = []

        os.makedirs(self.persist_dir, exist_ok=True)
        self._chroma_client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # 加载与索引
    # ------------------------------------------------------------------
    def load(self) -> None:
        """从 data_dir 加载所有 JSONL 知识文件到内存并构建 BM25。"""
        self.entries = list(self._iter_entries(self.data_dir))
        self._entry_index = {e.id: e for e in self.entries}
        self._build_bm25()

    @staticmethod
    def _iter_entries(data_dir: str):
        if not os.path.isdir(data_dir):
            raise FileNotFoundError(f"知识库目录不存在：{data_dir}")
        for fname in sorted(os.listdir(data_dir)):
            if not fname.endswith(".jsonl"):
                continue
            fpath = os.path.join(data_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                for lineno, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        yield KnowledgeEntry.model_validate(data)
                    except Exception as exc:
                        raise ValueError(
                            f"知识条目解析失败：{fpath}:{lineno} - {exc}"
                        ) from exc

    def _build_bm25(self) -> None:
        """基于条目的可检索文本构建 BM25 索引。"""
        if not self.entries:
            self._bm25 = None
            self._bm25_doc_ids = []
            return
        corpus_tokens = [_tokenize_zh(e.to_search_text()) for e in self.entries]
        self._bm25 = BM25Okapi(corpus_tokens)
        self._bm25_doc_ids = [e.id for e in self.entries]

    def reindex(self, force: bool = False) -> int:
        """把所有条目嵌入并写入 ChromaDB；返回实际写入的条目数。

        Args:
            force: True 时清空现有 collection 后全量重建；False 时仅写入"未存在"的条目。
        """
        if not self.entries:
            self.load()

        if force:
            try:
                self._chroma_client.delete_collection(self.collection_name)
            except Exception:
                pass
            self._collection = self._chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        existing_ids = set(self._collection.get(include=[]).get("ids", []))
        to_index = [e for e in self.entries if e.id not in existing_ids] if not force else self.entries
        if not to_index:
            return 0

        texts = [e.to_search_text() for e in to_index]
        vectors = self.embedding_client.embed_documents(texts)

        self._collection.add(
            ids=[e.id for e in to_index],
            embeddings=vectors,
            documents=texts,
            metadatas=[self._to_metadata(e) for e in to_index],
        )
        return len(to_index)

    @staticmethod
    def _to_metadata(entry: KnowledgeEntry) -> Dict[str, str]:
        """提取 ChromaDB 可索引的扁平元数据（仅原子值）。"""
        return {
            "category": entry.category,
            "topic": entry.topic,
            "region": entry.region,
            "confidence": entry.confidence,
            "time_window": entry.time_window or "",
            "source_org": entry.source.org,
        }

    # ------------------------------------------------------------------
    # 检索原子接口
    # ------------------------------------------------------------------
    def vector_search(
        self,
        query: str,
        top_k: int = 8,
        category: Optional[str] = None,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """向量检索：返回 (entry, similarity) 列表。

        相似度采用 1 - cosine_distance，范围 [0, 1]，越大越相似。
        """
        if self._collection.count() == 0:
            return []
        query_vec = self.embedding_client.embed_query(query)
        where = {"category": category} if category else None
        result = self._collection.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=where,
        )
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: List[Tuple[KnowledgeEntry, float]] = []
        for entry_id, dist in zip(ids, distances):
            entry = self._entry_index.get(entry_id)
            if not entry:
                continue
            similarity = max(0.0, 1.0 - float(dist))
            hits.append((entry, similarity))
        return hits

    def bm25_search(
        self,
        query: str,
        top_k: int = 8,
        category: Optional[str] = None,
    ) -> List[Tuple[KnowledgeEntry, float]]:
        """BM25 词法检索：返回 (entry, normalized_score) 列表，分数已归一化到 [0, 1]。"""
        if not self._bm25 or not self.entries:
            return []
        query_tokens = _tokenize_zh(query)
        scores = self._bm25.get_scores(query_tokens)
        max_score = max(scores) if len(scores) else 0.0
        if max_score <= 0:
            return []
        ranked = sorted(
            zip(self._bm25_doc_ids, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        hits: List[Tuple[KnowledgeEntry, float]] = []
        for entry_id, score in ranked:
            entry = self._entry_index.get(entry_id)
            if not entry or score <= 0:
                continue
            if category and entry.category != category:
                continue
            hits.append((entry, float(score) / float(max_score)))
            if len(hits) >= top_k:
                break
        return hits

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------
    def get_by_id(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """按 ID 精确查找知识条目，未命中返回 None。

        语义桥接模块通过 grade_id 直接命中权威条款，避免重复跑向量检索。
        """
        return self._entry_index.get(entry_id)

    def stats(self) -> Dict[str, int]:
        """返回知识库基本统计信息。"""
        from collections import Counter
        cat_count = Counter(e.category for e in self.entries)
        return {
            "total_entries": len(self.entries),
            "indexed_in_chroma": self._collection.count(),
            "by_category": dict(cat_count),
        }


import threading

_default_kb: Optional[KnowledgeBase] = None
_kb_lock = threading.Lock()


def get_knowledge_base(auto_index: bool = True) -> KnowledgeBase:
    """获取进程级单例知识库实例（首次调用时自动加载并增量索引）。

    用 double-checked locking 保护单例创建：LangGraph 并行调度多个工具时，
    若两个工具同时首次访问会触发 ChromaDB 的 PersistentClient 并发初始化 bug
    （RustBindingsAPI 'bindings' AttributeError），加锁后只有第一个调用真正
    建立单例，其它调用直接复用。
    """
    global _default_kb
    if _default_kb is not None:
        return _default_kb
    with _kb_lock:
        if _default_kb is None:
            kb = KnowledgeBase()
            kb.load()
            if auto_index:
                kb.reindex(force=False)
            _default_kb = kb
    return _default_kb


if __name__ == "__main__":
    kb = KnowledgeBase()
    kb.load()
    written = kb.reindex(force=False)
    print(f"新写入 ChromaDB 的条目数：{written}")
    print("知识库统计：", kb.stats())
