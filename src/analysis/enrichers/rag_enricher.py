"""RAG 富化器：把 SemanticLabel.grade_id 映射为权威影响描述与建议

设计原则：
- 不做向量检索（那是 Agent 用的），按 ID 精确查 KnowledgeBase
- 只在 grade_id 命中时填充 impact / citation，保证零幻觉
- 场景过滤：仅保留 entry.applicable_scene 命中当前场景的条目
"""

from typing import List, Optional

from src.analysis.schema import SemanticLabel
from src.rag.knowledge_base import KnowledgeBase, get_knowledge_base
from src.rag.schema import KnowledgeEntry


def enrich_with_rag(
    label: SemanticLabel,
    scene: Optional[str] = None,
    kb: Optional[KnowledgeBase] = None,
) -> SemanticLabel:
    """通过 grade_id 在 KB 中查权威条款，填充 impact/citation/source。

    Args:
        label: 分类器输出的 SemanticLabel
        scene: 当前场景（如 '出行'、'高空作业'），用于裁剪不相关 actions
        kb: 知识库实例（默认走单例）

    Returns:
        富化后的 SemanticLabel（原对象的拷贝；source 升级为 rule_plus_rag）
    """
    if not label.grade_id:
        return label
    kb = kb or get_knowledge_base()
    entry = kb.get_by_id(label.grade_id)
    if not entry:
        return label

    # 场景过滤：若指定了 scene 且本条不适用，则不富化
    if scene and entry.applicable_scene and scene not in entry.applicable_scene:
        return label

    return label.model_copy(update={
        "impact": entry.content,
        "citation": _build_citation(entry),
        "source": "rule_plus_rag",
    })


def _build_citation(entry: KnowledgeEntry) -> str:
    """构造紧凑的引用文本，如 'GB/T 28592-2012 §4.1（中国气象局）'。"""
    src = entry.source
    parts: List[str] = []
    if src.doc_title:
        parts.append(src.doc_title)
    if src.clause:
        parts.append(f"§{src.clause}")
    if src.org and src.org not in (src.doc_title or ""):
        parts.append(f"（{src.org}）")
    return " ".join(parts) if parts else (src.org or "未知出处")


if __name__ == "__main__":
    from src.analysis.classifiers.precipitation import classify_precipitation

    label = classify_precipitation(35.0, "24h")
    print("分级前：", label.model_dump())
    enriched = enrich_with_rag(label, scene="出行")
    print("\n富化后：", enriched.model_dump())
