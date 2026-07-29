"""Weaviate 客户端单例与 Chunk collection schema 管理。"""
import weaviate
from weaviate.classes.config import Configure, Property, DataType, Tokenization, VectorDistances

from app.config import get_config


# ---------- Chunk collection schema 定义 ----------

CHUNK_PROPERTIES = [
    Property(
        name="chunk_id",
        data_type=DataType.TEXT,
        tokenization=Tokenization.FIELD,
        description="分块唯一ID（UUID）",
    ),
    Property(
        name="file_id",
        data_type=DataType.TEXT,
        tokenization=Tokenization.FIELD,
        description="关联 agent files 表的 id",
    ),
    Property(
        name="namespace",
        data_type=DataType.TEXT,
        tokenization=Tokenization.FIELD,
        description="命名空间隔离（默认 default）",
    ),
    Property(
        name="session_id",
        data_type=DataType.TEXT,
        tokenization=Tokenization.FIELD,
        description="会话ID（scope=session 时有值）",
    ),
    Property(
        name="chunk_index",
        data_type=DataType.INT,
        description="分块序号（从0开始）",
    ),
    Property(
        name="text",
        data_type=DataType.TEXT,
        tokenization=Tokenization.WORD,
        description="分块文本内容（BM25 索引对象）",
    ),
    Property(
        name="line_start",
        data_type=DataType.INT,
        description="行号起点（从1开始）",
    ),
    Property(
        name="line_end",
        data_type=DataType.INT,
        description="行号终点",
    ),
    Property(
        name="filename",
        data_type=DataType.TEXT,
        tokenization=Tokenization.FIELD,
        description="原始文件名（展示用冗余）",
    ),
]


# ---------- 客户端单例 ----------

_client: weaviate.WeaviateClient | None = None


def get_client() -> weaviate.WeaviateClient:
    """获取 Weaviate 客户端（单例）。

    weaviate-client 4.x 需要显式 connect()，由 init_client() 在应用启动时调用。
    """
    if _client is None:
        raise RuntimeError("Weaviate 客户端未初始化，请先调用 init_client()")
    return _client


def init_client() -> weaviate.WeaviateClient:
    """初始化 Weaviate 客户端并创建 Chunk collection（如果不存在）。

    在 FastAPI lifespan 启动时调用。
    """
    global _client
    if _client is not None:
        return _client

    config = get_config()
    weaviate_cfg = config["weaviate"]
    url = weaviate_cfg["url"]

    # 解析 URL，提取 host 和 port
    # url 格式: http://localhost:8080
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8080

    _client = weaviate.connect_to_local(
        host=host,
        port=port,
        grpc_port=50051,
    )

    if not _client.is_ready():
        raise RuntimeError(f"Weaviate 未就绪: {url}")

    # 创建 Chunk collection（如果不存在）
    class_name = weaviate_cfg["class_name"]
    if not _client.collections.exists(class_name):
        distance_str = weaviate_cfg.get("distance", "cosine").lower()
        distance_map = {
            "cosine": VectorDistances.COSINE,
            "l2": VectorDistances.L2_SQUARED,
            "l2-squared": VectorDistances.L2_SQUARED,
            "dot": VectorDistances.DOT,
            "manhattan": VectorDistances.MANHATTAN,
            "hamming": VectorDistances.HAMMING,
        }
        distance_metric = distance_map.get(distance_str, VectorDistances.COSINE)

        _client.collections.create(
            name=class_name,
            description="文档分块，支持向量搜索和BM25关键词搜索",
            vectorizer_config=Configure.Vectorizer.none(),
            vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=distance_metric,
            ),
            properties=CHUNK_PROPERTIES,
        )
        print(f"[Weaviate] 已创建 collection: {class_name}")
    else:
        print(f"[Weaviate] collection 已存在: {class_name}")

    return _client


def close_client() -> None:
    """关闭 Weaviate 客户端连接。在 FastAPI lifespan 关闭时调用。"""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_collection():
    """获取 Chunk collection 对象。"""
    client = get_client()
    config = get_config()
    class_name = config["weaviate"]["class_name"]
    return client.collections.get(class_name)
