import csv
import io
import os
import tempfile
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_config
from app.vectorstore import add_documents, delete_document_chunks


def _get_splitter() -> RecursiveCharacterTextSplitter:
    config = get_config()
    chunk_cfg = config["chunking"]
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_cfg["chunk_size"],
        chunk_overlap=chunk_cfg["chunk_overlap"],
        separators=chunk_cfg["separators"],
    )


def process_upload(filename: str, content: bytes) -> dict:
    config = get_config()
    upload_cfg = config["upload"]

    ext = Path(filename).suffix.lower()
    if ext not in upload_cfg["allowed_extensions"]:
        raise ValueError(f"不支持的文件类型: {ext}，仅支持 {upload_cfg['allowed_extensions']}")

    # 覆盖策略：删除旧版本
    delete_document_chunks(filename)

    # 文件处理：小文件内存处理，大文件临时保存
    max_mem = upload_cfg["max_memory_size"]
    text = _read_content(filename, content, max_mem, upload_cfg["temp_directory"])

    # 分块：CSV 格式按行分块，其他格式使用文本分块器
    chunks = _split_csv_rows(text) if _is_csv_like(text) else _get_splitter().split_text(text)

    if not chunks:
        return {"filename": filename, "chunks": 0}

    # 构建元数据
    metadatas = [{"filename": filename, "chunk_index": i} for i in range(len(chunks))]

    # 写入向量库
    add_documents(texts=chunks, metadatas=metadatas)

    return {"filename": filename, "chunks": len(chunks)}


def _read_content(filename: str, content: bytes, max_memory_size: int, temp_dir: str) -> str:
    if len(content) <= max_memory_size:
        return content.decode("utf-8")

    # 超过阈值，保存到临时文件处理
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


def delete_document(filename: str) -> dict:
    removed = delete_document_chunks(filename)
    return {"filename": filename, "removed_chunks": removed}


def _is_csv_like(text: str) -> bool:
    """检测文本是否为 CSV/表格格式（逗号分隔，多行结构化数据）"""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return False
    comma_lines = sum(1 for l in lines if "," in l)
    return comma_lines / len(lines) >= 0.7


def _split_csv_rows(text: str) -> list[str]:
    """将 CSV 格式文本按行分块，每行一个 chunk，保留表头上下文"""
    reader = csv.reader(io.StringIO(text.strip()))
    rows = list(reader)
    if not rows:
        return []

    # 尝试识别表头（第一行）
    header = rows[0]
    has_header = any(keyword in "".join(header) for keyword in ["名称", "节日", "日期", "节气", "事件"])

    chunks = []
    start = 1 if has_header else 0
    header_text = ",".join(header) if has_header else None

    for i in range(start, len(rows)):
        row_text = ",".join(rows[i]).strip()
        if not row_text:
            continue
        # 如果有表头，在每个 chunk 前加上表头作为上下文
        if header_text:
            chunks.append(f"{header_text}\n{row_text}")
        else:
            chunks.append(row_text)

    return chunks
