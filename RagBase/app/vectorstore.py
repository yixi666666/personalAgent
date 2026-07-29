"""向量存储操作封装（基于 Weaviate）。

替代原 Chroma 实现，提供向量 CRUD、向量检索、混合检索、删除等功能。
"""
import os
from typing import Optional

import weaviate
from langchain_huggingface import HuggingFaceEmbeddings
from weaviate.classes.data import DataObject
from weaviate.classes.query import Filter, MetadataQuery

from app.config import get_config
from app.weaviate_client import get_collection

# Windows 上禁用符号链接，避免权限问题
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


# ---------- Embedding ----------

_embeddings: HuggingFaceEmbeddings | None = None


def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        config = get_config()
        model_name = config["embedding"]["model_name"]
        device = _detect_device()
        _embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
        )
    return _embeddings


def _detect_device() -> str:
    """检测可用设备：优先 GPU，不可用则回退 CPU。"""
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            print(f"[Embedding] 检测到 GPU: {device_name}，使用 CUDA 加速")
            return "cuda"
    except ImportError:
        pass
    print("[Embedding] 未检测到可用 GPU，使用 CPU 运行")
    return "cpu"


def embed_query(query: str) -> list[float]:
    """生成查询文本的向量。"""
    return get_embeddings().embed_query(query)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量生成文本向量。"""
    return get_embeddings().embed_documents(texts)


# ---------- 过滤条件构造 ----------

def build_filter(
    file_id: Optional[str] = None,
    namespace: Optional[str] = None,
    session_id: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[Filter]:
    """构造 Weaviate 过滤条件，所有条件为 AND 关系。"""
    filters = []
    if file_id:
        filters.append(Filter.by_property("file_id").equal(file_id))
    if namespace:
        filters.append(Filter.by_property("namespace").equal(namespace))
    if session_id:
        filters.append(Filter.by_property("session_id").equal(session_id))
    if filename:
        filters.append(Filter.by_property("filename").equal(filename))

    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    result = filters[0]
    for f in filters[1:]:
        result = result & f
    return result


# ---------- 写入 ----------

def add_chunks(chunks: list[dict], vectors: list[list[float]]) -> None:
    """批量写入分块到 Weaviate。

    Args:
        chunks: 分块数据列表，每个 dict 包含：
            chunk_id, file_id, namespace, session_id, chunk_index, text, line_start, line_end, filename
        vectors: 与 chunks 等长的向量列表
    """
    if len(chunks) != len(vectors):
        raise ValueError(f"chunks 数量({len(chunks)})与 vectors 数量({len(vectors)})不匹配")

    collection = get_collection()
    objects = [
        DataObject(properties=chunk, vector=vector)
        for chunk, vector in zip(chunks, vectors)
    ]
    collection.data.insert_many(objects)


# ---------- 检索 ----------

def search_by_vector(
    query: str,
    top_k: int = 5,
    file_id: Optional[str] = None,
    namespace: Optional[str] = None,
    session_id: Optional[str] = None,
    filename: Optional[str] = None,
) -> list[dict]:
    """纯向量检索。

    返回结果按相似度从高到低排序，score 为 cosine 距离（越小越相似）。
    """
    collection = get_collection()
    query_vector = embed_query(query)
    filters = build_filter(file_id, namespace, session_id, filename)

    kwargs = {
        "near_vector": query_vector,
        "limit": top_k,
        "return_metadata": MetadataQuery(distance=True),
    }
    if filters is not None:
        kwargs["filters"] = filters

    result = collection.query.near_vector(**kwargs)

    search_results = []
    for obj in result.objects:
        search_results.append({
            "chunk_id": obj.properties.get("chunk_id", ""),
            "file_id": obj.properties.get("file_id", ""),
            "content": obj.properties.get("text", ""),
            "metadata": {
                "filename": obj.properties.get("filename", ""),
                "file_id": obj.properties.get("file_id", ""),
                "namespace": obj.properties.get("namespace", ""),
                "session_id": obj.properties.get("session_id", ""),
                "chunk_index": obj.properties.get("chunk_index", 0),
                "line_start": obj.properties.get("line_start", 0),
                "line_end": obj.properties.get("line_end", 0),
            },
            "score": float(obj.metadata.distance) if obj.metadata.distance is not None else 0.0,
        })
    return search_results


def hybrid_search(
    query: str,
    top_k: int = 5,
    alpha: float = 0.5,
    file_id: Optional[str] = None,
    namespace: Optional[str] = None,
    session_id: Optional[str] = None,
    filename: Optional[str] = None,
) -> list[dict]:
    """混合检索（向量 + BM25 关键词）。

    Args:
        query: 查询文本（同时用于关键词搜索和向量化）
        top_k: 返回结果数
        alpha: 0=纯BM25, 1=纯向量, 0.5=混合
    """
    collection = get_collection()
    query_vector = embed_query(query)
    filters = build_filter(file_id, namespace, session_id, filename)

    kwargs = {
        "query": query,
        "vector": query_vector,
        "alpha": alpha,
        "limit": top_k,
        "return_metadata": MetadataQuery(score=True, explain_score=False),
    }
    if filters is not None:
        kwargs["filters"] = filters

    result = collection.query.hybrid(**kwargs)

    search_results = []
    for obj in result.objects:
        search_results.append({
            "chunk_id": obj.properties.get("chunk_id", ""),
            "file_id": obj.properties.get("file_id", ""),
            "text": obj.properties.get("text", ""),
            "line_start": obj.properties.get("line_start", 0),
            "line_end": obj.properties.get("line_end", 0),
            "filename": obj.properties.get("filename", ""),
            "namespace": obj.properties.get("namespace", ""),
            "session_id": obj.properties.get("session_id", ""),
            "score": float(obj.metadata.score) if obj.metadata.score is not None else 0.0,
        })
    return search_results


# ---------- 删除 ----------

def delete_by_file_id(file_id: str) -> int:
    """按 file_id 物理删除所有分块，返回删除数量。"""
    collection = get_collection()
    result = collection.data.delete_many(
        where=Filter.by_property("file_id").equal(file_id)
    )
    return result.successful


def delete_by_filename(filename: str) -> int:
    """按 filename 物理删除所有分块（旧接口兼容），返回删除数量。"""
    collection = get_collection()
    result = collection.data.delete_many(
        where=Filter.by_property("filename").equal(filename)
    )
    return result.successful


# ---------- 查询 ----------

def list_documents() -> list[dict]:
    """列出所有文档（按 filename 聚合，兼容旧接口格式）。"""
    collection = get_collection()
    result = collection.query.fetch_objects(
        limit=10000,
        return_properties=["filename", "file_id"],
    )

    file_chunks: dict[str, dict] = {}
    for obj in result.objects:
        filename = obj.properties.get("filename", "")
        file_id = obj.properties.get("file_id", "")
        key = filename
        if key not in file_chunks:
            file_chunks[key] = {"filename": filename, "chunks": 0, "file_id": file_id}
        file_chunks[key]["chunks"] += 1

    return list(file_chunks.values())


def get_document_by_file_id(file_id: str) -> dict | None:
    """按 file_id 查询文档分块数。"""
    collection = get_collection()
    result = collection.query.fetch_objects(
        limit=10000,
        filters=Filter.by_property("file_id").equal(file_id),
        return_properties=["filename", "file_id"],
    )

    if not result.objects:
        return None

    filename = result.objects[0].properties.get("filename", "")
    return {
        "file_id": file_id,
        "filename": filename,
        "chunks": len(result.objects),
    }
