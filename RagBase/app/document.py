"""文档处理：分块（带行号追踪）+ 索引写入。"""
import bisect
import os
import tempfile
import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_config
from app.oss import get_storage
from app.vectorstore import add_chunks, delete_by_file_id, delete_by_filename, embed_texts


# ---------- 分块器 ----------

def _get_splitter() -> RecursiveCharacterTextSplitter:
    config = get_config()
    chunk_cfg = config["chunking"]
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_cfg["chunk_size"],
        chunk_overlap=chunk_cfg["chunk_overlap"],
        separators=chunk_cfg["separators"],
    )


def split_text_with_lines(text: str) -> list[dict]:
    """分块并记录每个 chunk 的行号区间。

    Returns:
        [{"text": "...", "line_start": 1, "line_end": 5}, ...]
        行号从 1 开始。
    """
    if not text:
        return []

    # 1. 记录每行的起始字符偏移（0-indexed）
    lines = text.split('\n')
    line_offsets = []  # line_offsets[i] = 第 i 行（0-indexed）的起始字符偏移
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line) + 1  # +1 for '\n'

    # 2. 用 splitter 分块
    splitter = _get_splitter()
    chunks = splitter.split_text(text)

    # 3. 对每个 chunk，通过字符偏移映射回行号
    result = []
    search_start = 0
    for chunk_text in chunks:
        # 在原文中查找 chunk 的起始位置（从上一次查找位置开始，避免重复匹配）
        chunk_start = text.find(chunk_text, search_start)
        if chunk_start == -1:
            # 回退：从头查找
            chunk_start = text.find(chunk_text)
            if chunk_start == -1:
                # 极端情况：找不到，跳过
                continue
        chunk_end = chunk_start + len(chunk_text)

        # 通过二分查找确定行号（1-indexed）
        # line_offsets[i] <= chunk_start 的最大 i，即 chunk_start 所在行
        line_start_idx = bisect.bisect_right(line_offsets, chunk_start) - 1
        # line_offsets[i] <= chunk_end - 1 的最大 i，即 chunk_end 所在行
        line_end_idx = bisect.bisect_right(line_offsets, chunk_end - 1) - 1

        result.append({
            "text": chunk_text,
            "line_start": line_start_idx + 1,  # 转为 1-indexed
            "line_end": line_end_idx + 1,
        })

        # 下次查找从当前 chunk 起始位置 +1 开始，避免重叠 chunk 重复匹配
        search_start = chunk_start + 1

    return result


# ---------- 文件读取 ----------

def _read_content(filename: str, content: bytes) -> str:
    """读取文件内容为文本。小文件内存处理，大文件临时保存。"""
    config = get_config()
    upload_cfg = config["upload"]
    max_mem = upload_cfg["max_memory_size"]

    if len(content) <= max_mem:
        return content.decode("utf-8")

    # 超过阈值，保存到临时文件处理
    temp_dir = upload_cfg["temp_directory"]
    Path(temp_dir).mkdir(parents=True, exist_ok=True)
    temp_path = os.path.join(temp_dir, filename)
    try:
        with open(temp_path, "wb") as f:
            f.write(content)
        with open(temp_path, "r", encoding="utf-8") as f:
            text = f.read()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    return text


def _read_content_from_oss(oss_key: str) -> str:
    """从 OSS 读取文件内容为文本。"""
    storage = get_storage()
    content = storage.get(oss_key)
    return content.decode("utf-8")


# ---------- 索引写入 ----------

def _build_chunks_metadata(
    chunks: list[dict],
    file_id: str,
    namespace: str,
    session_id: str,
    filename: str,
) -> list[dict]:
    """构建写入 Weaviate 的分块元数据列表。"""
    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "chunk_id": str(uuid.uuid4()),
            "file_id": file_id,
            "namespace": namespace,
            "session_id": session_id,
            "chunk_index": i,
            "text": chunk["text"],
            "line_start": chunk["line_start"],
            "line_end": chunk["line_end"],
            "filename": filename,
        })
    return result


def _index_text(
    text: str,
    file_id: str,
    namespace: str,
    session_id: str,
    filename: str,
) -> list[dict]:
    """分块 + 向量化 + 写入 Weaviate，返回 chunk 列表。"""
    # 分块（带行号）
    chunks = split_text_with_lines(text)
    if not chunks:
        return []

    # 构建元数据
    chunks_metadata = _build_chunks_metadata(chunks, file_id, namespace, session_id, filename)

    # 批量生成向量
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)

    # 写入 Weaviate
    add_chunks(chunks_metadata, vectors)

    # 返回 chunk 摘要（不含完整 text，避免响应过大）
    return [
        {
            "chunk_id": c["chunk_id"],
            "chunk_index": c["chunk_index"],
            "line_start": c["line_start"],
            "line_end": c["line_end"],
        }
        for c in chunks_metadata
    ]


# ---------- 旧接口兼容（POST /v1/upload） ----------

def process_upload(filename: str, content: bytes) -> dict:
    """旧接口：上传文档并写入向量库。

    内部自动生成 file_id，namespace="default"，session_id=""。
    文件内容存入 local_oss 便于后续管理。
    """
    config = get_config()
    upload_cfg = config["upload"]

    ext = Path(filename).suffix.lower()
    if ext not in upload_cfg["allowed_extensions"]:
        raise ValueError(f"不支持的文件类型: {ext}，仅支持 {upload_cfg['allowed_extensions']}")

    # 生成 file_id 和 oss_key
    file_id = str(uuid.uuid4())
    namespace = "default"
    session_id = ""
    oss_key = f"uploads/{namespace}/legacy/{file_id}{ext}"

    # 覆盖策略：按 filename 删除旧版本
    delete_by_filename(filename)

    # 存入 local_oss
    storage = get_storage()
    storage.put(oss_key, content)

    # 读取文本
    text = _read_content(filename, content)

    # 索引写入
    chunks = _index_text(text, file_id, namespace, session_id, filename)

    return {"file_id": file_id, "filename": filename, "chunks": len(chunks)}


def delete_document(filename: str) -> dict:
    """旧接口：按 filename 删除文档。"""
    removed = delete_by_filename(filename)
    return {"filename": filename, "removed_chunks": removed}


# ---------- 新接口（POST /v1/index） ----------

def process_index(
    file_id: str,
    namespace: str,
    session_id: str,
    filename: str,
    oss_key: str,
) -> dict:
    """新接口：从 OSS 读取文件并索引到 Weaviate。

    覆盖策略：按 file_id 删除旧版本。
    """
    # 覆盖策略：按 file_id 删除旧版本
    delete_by_file_id(file_id)

    # 从 OSS 读取
    text = _read_content_from_oss(oss_key)

    # 索引写入
    chunks = _index_text(text, file_id, namespace, session_id, filename)

    return {
        "file_id": file_id,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
