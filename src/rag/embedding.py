"""向量嵌入封装

通过 OpenAI 兼容协议调用 SiliconFlow（或其他兼容平台）的嵌入接口，
为 RAG 检索提供统一的 ``embed_query`` / ``embed_documents`` 接口。
"""

from typing import List

from openai import OpenAI

from src.config.settings import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
)


class EmbeddingClient:
    """轻量嵌入客户端：批量编码文本为向量。"""

    def __init__(
        self,
        model: str = EMBEDDING_MODEL,
        api_key: str = EMBEDDING_API_KEY,
        base_url: str = EMBEDDING_BASE_URL,
        batch_size: int = 16,
    ):
        self.model = model
        self.batch_size = batch_size
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """对一批文本进行嵌入，自动分批以适配服务端限制。"""
        if not texts:
            return []
        all_vectors: List[List[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            resp = self._client.embeddings.create(model=self.model, input=batch)
            all_vectors.extend([item.embedding for item in resp.data])
        return all_vectors

    def embed_query(self, text: str) -> List[float]:
        """对单条查询文本进行嵌入。"""
        if not text:
            return []
        resp = self._client.embeddings.create(model=self.model, input=[text])
        return resp.data[0].embedding


_default_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    """获取进程级的默认嵌入客户端单例。"""
    global _default_client
    if _default_client is None:
        _default_client = EmbeddingClient()
    return _default_client


if __name__ == "__main__":
    client = get_embedding_client()
    sample = ["小雨是指 24 小时降水量小于 10 毫米的降水", "高空作业风力 6 级及以上应停止"]
    vecs = client.embed_documents(sample)
    print(f"模型: {client.model}, 维度: {len(vecs[0])}")
    print(f"前 8 维示例: {vecs[0][:8]}")
