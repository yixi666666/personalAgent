import os
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from app.config import get_config

# Windows 上禁用符号链接，避免权限问题
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def _detect_device() -> str:
    """检测可用设备：优先 GPU，不可用则回退 CPU"""
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


_embeddings = None
_vectorstore = None


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


def _get_expected_dim() -> int:
    """获取当前 embedding 模型的输出维度"""
    emb = get_embeddings()
    test_vec = emb.embed_query("test")
    return len(test_vec)


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        config = get_config()
        persist_dir = config["vectorstore"]["persist_directory"]
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        emb = get_embeddings()
        expected_dim = _get_expected_dim()

        # 检查已有 collection 的维度是否匹配，不匹配则删除旧 collection 重建
        try:
            vs = Chroma(
                embedding_function=emb,
                persist_directory=persist_dir,
            )
            existing_dim = vs._collection.metadata.get("hnsw:dim")
            if existing_dim is not None and int(existing_dim) != expected_dim:
                print(f"Embedding 维度不匹配 (现有={existing_dim}, 期望={expected_dim})，重建向量库...")
                # 删除旧 collection，而不是删除整个数据库目录
                vs._client.delete_collection(vs._collection.name)
                vs = Chroma(
                    embedding_function=emb,
                    persist_directory=persist_dir,
                )
            _vectorstore = vs
        except Exception:
            # 如果加载失败，尝试删除整个数据库目录重建
            shutil.rmtree(persist_dir, ignore_errors=True)
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            _vectorstore = Chroma(
                embedding_function=emb,
                persist_directory=persist_dir,
            )
    return _vectorstore


def delete_document_chunks(filename: str) -> int:
    vs = get_vectorstore()
    collection = vs._collection
    results = collection.get(where={"filename": filename})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def add_documents(texts: list[str], metadatas: list[dict]) -> None:
    vs = get_vectorstore()
    vs.add_texts(texts=texts, metadatas=metadatas)


def search_documents(query: str, top_k: int = 5, score_threshold: float | None = None) -> list[dict]:
    vs = get_vectorstore()
    # 多取一些候选，再按阈值过滤
    fetch_k = top_k * 3 if score_threshold is not None else top_k
    results = vs.similarity_search_with_score(query, k=fetch_k)
    search_results = []
    for doc, score in results:
        # Chroma 返回的是 L2 距离，越小越相似；阈值过滤掉距离过大的结果
        if score_threshold is not None and score > score_threshold:
            continue
        search_results.append({
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score),
        })
        if len(search_results) >= top_k:
            break
    return search_results


def list_documents() -> list[dict]:
    vs = get_vectorstore()
    collection = vs._collection
    results = collection.get(include=["metadatas"])
    file_chunks: dict[str, int] = {}
    for meta in results.get("metadatas", []):
        filename = meta.get("filename", "")
        if filename:
            file_chunks[filename] = file_chunks.get(filename, 0) + 1
    return [{"filename": f, "chunks": c} for f, c in file_chunks.items()]
