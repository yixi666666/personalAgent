"""Embedding 服务：基于 bge-small-zh-v1.5 的本地向量编码。

用于高校语义匹配和 Fact 向量召回，与数据库中已有的向量使用同一模型。
"""

import logging
import os
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# 抑制 sentence_transformers 库的冗余日志
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

# 模型路径（相对于项目根目录）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DEFAULT_MODEL_PATH = os.path.join(_PROJECT_ROOT, "RagBase", "model_cache", "bge-small-zh-v1.5")


class EmbeddingService:
    """单例 embedding 服务，懒加载模型"""

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(_DEFAULT_MODEL_PATH)
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """批量编码文本，返回 L2 归一化后的向量矩阵"""
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return np.array(embeddings, dtype=np.float32)

    def encode_one(self, text: str) -> np.ndarray:
        """编码单条文本，返回 L2 归一化后的一维向量"""
        return self.encode([text])[0]


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
