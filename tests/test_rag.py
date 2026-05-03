"""RAG 检索模块测试

包含两类测试：
1. 知识库加载与统计：不依赖网络
2. 混合检索结果：会调用嵌入模型 API（消耗少量 Token）

运行：
    python -m tests.test_rag
"""

from src.rag.knowledge_base import KnowledgeBase, get_knowledge_base
from src.rag.retriever import HybridRetriever, format_hits_for_llm


# 期望命中（topic 或 id 子串）的测试用例
RETRIEVAL_CASES = [
    {
        "query": "24小时降水30毫米属于什么级别",
        "expected_topic": "降水等级",
        "expected_category": "grading_standard",
    },
    {
        "query": "高空作业风力达到几级要停止",
        "expected_topic": "高空作业",
        "expected_category": "operation_guideline",
    },
    {
        "query": "什么是雷暴",
        "expected_topic": "强对流",
        "expected_category": "term_definition",
    },
    {
        "query": "高温天气户外作业有什么规定",
        "expected_topic": "户外作业",
        "expected_category": "operation_guideline",
    },
    {
        "query": "什么是台风",
        "expected_topic": "热带气旋",
        "expected_category": "term_definition",
    },
    {
        "query": "AQI 200 是什么意思",
        "expected_topic": "空气质量",
        "expected_category": "term_definition",
    },
    {
        "query": "20 度该穿什么衣服",
        "expected_topic": "穿衣建议",
        "expected_category": "operation_guideline",
    },
    {
        "query": "3 级风是什么概念",
        "expected_topic": "风力等级",
        "expected_category": "grading_standard",
    },
]


def test_knowledge_base_load():
    """测试知识库加载与统计。"""
    print("=" * 80)
    print("测试 1：知识库加载与统计")
    print("=" * 80)
    kb = KnowledgeBase()
    kb.load()
    stats = kb.stats()
    print(f"  总条目数：{stats['total_entries']}")
    print(f"  分类分布：{stats['by_category']}")
    assert stats["total_entries"] > 0, "知识库为空"
    assert "grading_standard" in stats["by_category"]
    assert "term_definition" in stats["by_category"]
    assert "operation_guideline" in stats["by_category"]
    print("  PASS\n")
    return kb


def test_indexing(kb: KnowledgeBase):
    """测试 ChromaDB 索引（首次会调用嵌入 API）。"""
    print("=" * 80)
    print("测试 2：ChromaDB 索引（首次需调用嵌入 API）")
    print("=" * 80)
    written = kb.reindex(force=False)
    stats = kb.stats()
    print(f"  本次写入：{written} 条")
    print(f"  ChromaDB 累计已索引：{stats['indexed_in_chroma']} 条")
    assert stats["indexed_in_chroma"] == stats["total_entries"], "索引数与条目数不一致"
    print("  PASS\n")


def test_hybrid_retrieval():
    """测试混合检索：每条查询应在 Top-3 中命中预期 topic。"""
    print("=" * 80)
    print("测试 3：混合检索（向量 + BM25）")
    print("=" * 80)
    retriever = HybridRetriever()
    pass_count = 0
    for i, case in enumerate(RETRIEVAL_CASES, 1):
        query = case["query"]
        hits = retriever.retrieve(query, top_k=3)
        hit_topics = [h.entry.topic for h in hits]
        is_pass = case["expected_topic"] in hit_topics
        if is_pass:
            pass_count += 1
        status = "PASS" if is_pass else "FAIL"
        print(f"\n  [{i}] {query}")
        print(f"      期望 topic: {case['expected_topic']} | 实际 Top-3 topics: {hit_topics}  [{status}]")
        if hits:
            top = hits[0]
            print(f"      Top-1: {top.entry.title} (融合分 {top.score}, 向量 {top.vector_score}, BM25 {top.bm25_score})")
    print(f"\n  通过率：{pass_count}/{len(RETRIEVAL_CASES)}")
    print("  PASS" if pass_count == len(RETRIEVAL_CASES) else f"  FAIL（{len(RETRIEVAL_CASES) - pass_count} 条未命中预期 topic）")


def test_category_filter():
    """测试 category 过滤是否生效。"""
    print("\n" + "=" * 80)
    print("测试 4：category 过滤")
    print("=" * 80)
    retriever = HybridRetriever()
    hits = retriever.retrieve("台风", top_k=3, category="term_definition")
    cats = [h.entry.category for h in hits]
    print(f"  仅检索 term_definition：{cats}")
    assert all(c == "term_definition" for c in cats), "类别过滤未生效"
    print("  PASS")


def main():
    kb = test_knowledge_base_load()
    test_indexing(kb)
    # 后续检索测试复用 kb，避免重复加载
    import src.rag.retriever as ret_mod
    ret_mod._default_retriever = HybridRetriever(kb=kb)
    test_hybrid_retrieval()
    test_category_filter()


if __name__ == "__main__":
    main()
