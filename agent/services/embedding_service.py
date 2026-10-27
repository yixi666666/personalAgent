"""Embedding 服务：基于 SiliconFlow 远程 API（BAAI/bge-large-zh-v1.5）的向量编码。

用于高校语义匹配和 Fact 向量召回，与数据库中已有的向量使用同一模型。
接口与原本地 sentence_transformers 版本保持一致（encode / encode_one）。
"""

import logging
from typing import Optional

import numpy as np
from openai import OpenAI

from agent.services.model_service import get_embedding_provider

logger = logging.getLogger(__name__)

# 单次请求批量文本数（性能参数，非模型配置）
EMBEDDING_BATCH_SIZE = 32


class EmbeddingService:
    """单例 embedding 服务，懒加载远程客户端"""

    def __init__(self):
        self._client: Optional[OpenAI] = None
        self._model: str = ""

    def _get_client(self) -> OpenAI:
        if self._client is None:
            provider = get_embedding_provider()
            api_key = provider.get("api_key")
            if not api_key:
                raise ValueError(
                    "embedding 模型 api_key 未配置或解密失败，请检查 models_configs 表"
                )
            self._model = provider["name"]
            full_base_url = (
                provider["base_url"].rstrip("/")
                + provider.get("api_prefix", "").rstrip("/")
            )
            self._client = OpenAI(
                base_url=full_base_url,
                api_key=api_key,
            )
        return self._client

    def _embed(self, texts: list[str]) -> np.ndarray:
        """调用远程 API 批量编码，返回 L2 归一化后的向量矩阵

        数据库中的存量向量（sentence_transformers normalize_embeddings=True）
        均为 L2 归一化格式，这里对 API 返回向量统一归一化对齐（幂等操作）。
        """
        batch_size = EMBEDDING_BATCH_SIZE

        client = self._get_client()
        vectors: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = client.embeddings.create(model=self._model, input=batch)
            # data 按 input 顺序返回，按 index 排序后依次取 embedding
            ordered = sorted(resp.data, key=lambda item: item.index)
            vectors.extend(item.embedding for item in ordered)

        arr = np.array(vectors, dtype=np.float32)
        # L2 归一化（零向量保护，避免除零）
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return arr / norms

    def encode(self, texts: list[str]) -> np.ndarray:
        """批量编码文本，返回 L2 归一化后的向量矩阵"""
        if not texts:
            return np.zeros((0, 1024), dtype=np.float32)
        return self._embed(texts)

    def encode_one(self, text: str) -> np.ndarray:
        """编码单条文本，返回 L2 归一化后的一维向量"""
        return self.encode([text])[0]


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
