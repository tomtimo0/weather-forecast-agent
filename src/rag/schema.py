"""RAG 知识条目与检索结果的数据模型"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


KnowledgeCategory = Literal[
    "term_definition",      # 术语定义（如"小雨"是什么）
    "grading_standard",     # 分级标准（如降水量级、风力蒲福级）
    "operation_guideline",  # 作业/出行规范（如高空作业适宜条件）
]


class KnowledgeSource(BaseModel):
    """知识条目的出处溯源信息。"""

    org: str = Field(description="发布机构，如'中国气象局'、'WMO'、'国家标准 GB/T xxxxx'")
    doc_title: Optional[str] = Field(default=None, description="文档标题")
    clause: Optional[str] = Field(default=None, description="条款号或段落，如'5.2.1'")
    publish_date: Optional[str] = Field(default=None, description="发布日期 YYYY-MM-DD")
    url: Optional[str] = Field(default=None, description="原文链接")


class KnowledgeEntry(BaseModel):
    """单条知识条目（知识库中的最小存储单元）。"""

    id: str = Field(description="全局唯一 ID，建议使用 'category_topic_subkey_v版本' 形式")
    category: KnowledgeCategory = Field(description="知识类别")
    topic: str = Field(description="主题标签，如'降水等级'、'风力等级'、'高空作业'")
    region: str = Field(default="CN", description="适用地区，如 'CN'、'WMO'、'global'")

    title: str = Field(description="条目简短标题，用于检索召回展示")
    content: str = Field(description="知识正文，可包含定义、阈值表、解释等")

    # 可选的结构化字段：用于精确匹配 / 元数据过滤
    time_window: Optional[str] = Field(
        default=None, description="时间窗口，如 '24h'、'12h'、'1h'，用于分级标准"
    )
    applicable_scene: List[str] = Field(
        default_factory=list, description="适用场景标签，如 ['出行', '施工', '农业']"
    )
    keywords: List[str] = Field(
        default_factory=list, description="关键词列表，用于 BM25 召回增强"
    )

    source: KnowledgeSource = Field(description="出处与版权信息")
    confidence: Literal["official", "industry", "common"] = Field(
        default="common",
        description="可信级别：official 官方/国标，industry 行业规范，common 通用常识",
    )
    version: str = Field(default="1.0.0", description="条目版本号，便于演进追踪")

    def to_search_text(self) -> str:
        """拼接成用于向量化与 BM25 索引的文本。"""
        scene = "、".join(self.applicable_scene) if self.applicable_scene else ""
        kw = "、".join(self.keywords) if self.keywords else ""
        parts = [
            f"【{self.topic}】{self.title}",
            self.content,
        ]
        if scene:
            parts.append(f"适用场景：{scene}")
        if kw:
            parts.append(f"关键词：{kw}")
        if self.time_window:
            parts.append(f"时间窗口：{self.time_window}")
        return "\n".join(parts)


class RetrievalHit(BaseModel):
    """单条检索命中结果。"""

    entry: KnowledgeEntry = Field(description="命中的知识条目")
    score: float = Field(description="融合后的最终相关度分数，越高越相关")
    vector_score: Optional[float] = Field(default=None, description="向量相似度分数")
    bm25_score: Optional[float] = Field(default=None, description="BM25 词法相似度分数")
    rank: int = Field(description="在本次检索结果中的排名（从 1 起）")
