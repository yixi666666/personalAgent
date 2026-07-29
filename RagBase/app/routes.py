"""RagBase 路由定义。

保留旧接口（兼容）+ 新增接口（支持完整文件上传流程）。

认证策略：
- 写操作需 Authorization：POST /v1/upload, POST /v1/index, DELETE /v1/documents, DELETE /v1/vectors, PUT /v1/oss
- 读操作不需要认证
"""
import time
from pathlib import Path

import openai
from fastapi import APIRouter, Body, File, Header, HTTPException, Path as FastPath, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.config import get_config, get_upload_token
from app.document import delete_document, process_index, process_upload
from app.llm import chat
from app.oss import get_storage
from app.vectorstore import (
    delete_by_file_id,
    get_document_by_file_id,
    hybrid_search,
    list_documents,
    search_by_vector,
)
from app.weaviate_client import get_client


router = APIRouter()


# ---------- 认证工具 ----------

def verify_token(authorization: str | None) -> None:
    """校验 Authorization Bearer token。"""
    if authorization is None:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    try:
        expected_token = get_upload_token()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if token != expected_token:
        raise HTTPException(status_code=403, detail="无效的 API Token")


# ---------- GET /health ----------
@router.get("/health")
def health_check():
    """检查 RagBase 服务及 Weaviate 连通性。"""
    try:
        client = get_client()
        weaviate_status = "ok" if client.is_ready() else "not_ready"
    except Exception as e:
        weaviate_status = f"error: {e}"
    return {"status": "ok", "weaviate": weaviate_status}


# ---------- POST /v1/upload（旧接口，兼容） ----------
@router.post("/v1/upload")
async def upload_document(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    """上传文档并写入向量库（需 Authorization 鉴权，同名文件覆盖旧版本）。"""
    verify_token(authorization)

    content = await file.read()
    filename = file.filename
    try:
        result = process_upload(filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"code": 0, "message": "success", "data": result}


# ---------- GET /v1/documents（旧接口，兼容） ----------
@router.get("/v1/documents")
def get_documents():
    """查看当前已上传的文档列表。"""
    docs = list_documents()
    return {"code": 0, "message": "success", "data": docs}


# ---------- GET /v1/documents/{file_id}（新接口） ----------
@router.get("/v1/documents/{file_id}")
def get_document(file_id: str = FastPath(..., description="文件ID")):
    """按 file_id 查询文档分块数。"""
    doc = get_document_by_file_id(file_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
    return {"code": 0, "message": "success", "data": doc}


# ---------- DELETE /v1/documents（旧接口，兼容） ----------
@router.delete("/v1/documents")
def delete_documents(filename: str = Query(..., description="要删除的文件名")):
    """删除指定文档的所有向量分块。"""
    result = delete_document(filename)
    return {"code": 0, "message": "success", "data": result}


# ---------- DELETE /v1/vectors（新接口） ----------
@router.delete("/v1/vectors")
def delete_vectors(
    file_id: str = Query(..., description="文件ID"),
    authorization: str = Header(None),
):
    """按 file_id 物理删除所有向量分块。"""
    verify_token(authorization)
    deleted_count = delete_by_file_id(file_id)
    return {"code": 0, "message": "success", "data": {"file_id": file_id, "deleted_count": deleted_count}}


# ---------- POST /v1/search（旧接口，兼容） ----------
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    file_id: str | None = None
    namespace: str | None = None
    session_id: str | None = None


@router.post("/v1/search")
def search(req: SearchRequest):
    """纯向量检索。"""
    config = get_config()
    top_k = req.top_k or config["search"]["top_k"]
    results = search_by_vector(
        query=req.query,
        top_k=top_k,
        file_id=req.file_id,
        namespace=req.namespace,
        session_id=req.session_id,
    )
    return {"code": 0, "message": "success", "data": results}


# ---------- POST /v1/hybrid-search（新接口） ----------
class HybridSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    alpha: float | None = None
    file_id: str | None = None
    namespace: str | None = None
    session_id: str | None = None


@router.post("/v1/hybrid-search")
def hybrid_search_endpoint(req: HybridSearchRequest):
    """混合检索（向量 + BM25 关键词）。"""
    config = get_config()
    top_k = req.top_k or config["search"]["top_k"]
    alpha = req.alpha if req.alpha is not None else config["search"]["hybrid_alpha"]
    results = hybrid_search(
        query=req.query,
        top_k=top_k,
        alpha=alpha,
        file_id=req.file_id,
        namespace=req.namespace,
        session_id=req.session_id,
    )
    return {"code": 0, "message": "success", "data": results}


# ---------- POST /v1/chat（旧接口，保留用于测试） ----------
class ChatRequest(BaseModel):
    query: str
    model: str | None = None
    top_k: int = 5


@router.post("/v1/chat")
def chat_endpoint(req: ChatRequest):
    """基于检索增强生成（RAG）的问答。"""
    config = get_config()
    top_k = req.top_k or config["search"]["top_k"]

    # 使用混合检索（默认 alpha=1.0 纯向量，保持与旧行为一致）
    results = hybrid_search(query=req.query, top_k=top_k, alpha=1.0)

    # 构建上下文
    context_parts = []
    for r in results:
        filename = r.get("filename", "unknown")
        line_start = r.get("line_start", 0)
        line_end = r.get("line_end", 0)
        context_parts.append(f"[来源: {filename} 行{line_start}-{line_end}]\n{r['text']}")
    context = "\n\n---\n\n".join(context_parts)

    # 调用 LLM
    try:
        answer = chat(req.query, context, model=req.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except openai.APIConnectionError:
        raise HTTPException(status_code=502, detail="无法连接到 LLM 服务")
    except openai.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"LLM 服务返回错误: {e.status_code}")

    sources = list({r.get("filename", "unknown") for r in results})

    return {
        "code": 0,
        "message": "success",
        "data": {
            "answer": answer,
            "sources": sources,
        },
    }


# ---------- POST /v1/index（新接口） ----------
class IndexRequest(BaseModel):
    file_id: str
    namespace: str = "default"
    session_id: str = ""
    filename: str
    oss_key: str


@router.post("/v1/index")
def index_document(req: IndexRequest, authorization: str = Header(None)):
    """触发索引：从 OSS 读取文件，分块并写入 Weaviate。"""
    verify_token(authorization)
    try:
        result = process_index(
            file_id=req.file_id,
            namespace=req.namespace,
            session_id=req.session_id,
            filename=req.filename,
            oss_key=req.oss_key,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "success", "data": result}


# ---------- OSS 模拟接口 ----------

@router.put("/v1/oss/{oss_key:path}")
async def oss_put(oss_key: str, request: Request, authorization: str = Header(None)):
    """上传文件到本地 OSS（写操作需认证）。"""
    verify_token(authorization)
    content = await request.body()
    storage = get_storage()
    storage.put(oss_key, content)
    return {"code": 0, "message": "success", "data": {"oss_key": oss_key, "size": len(content)}}


@router.get("/v1/oss/{oss_key:path}")
def oss_get(oss_key: str):
    """从本地 OSS 下载文件。"""
    storage = get_storage()
    try:
        content = storage.get(oss_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"OSS 对象不存在: {oss_key}")
    return Response(content=content, media_type="application/octet-stream")


@router.head("/v1/oss/{oss_key:path}")
def oss_head(oss_key: str):
    """检查本地 OSS 文件存在性。"""
    storage = get_storage()
    info = storage.head(oss_key)
    if not info["exists"]:
        raise HTTPException(status_code=404, detail=f"OSS 对象不存在: {oss_key}")
    return Response(headers={"X-File-Size": str(info["size"]), "X-File-Exists": "true"})


# ---------- POST /v1/test（保留，增加 hybrid-search） ----------
@router.post("/v1/test")
def test_endpoint(req: dict = Body(default={})):
    """通用接口测试端点，根据 target 调用对应接口并返回结果。"""
    target = req.get("target", "")
    params = req.get("params", {})

    results = {}
    t0 = time.time()

    try:
        if target == "health":
            results["health"] = _test_health()
        elif target == "documents":
            results["documents"] = _test_documents()
        elif target == "search":
            results["search"] = _test_search(params)
        elif target == "hybrid-search":
            results["hybrid-search"] = _test_hybrid_search(params)
        elif target == "chat":
            results["chat"] = _test_chat(params)
        elif target == "all":
            results["health"] = _test_health()
            results["documents"] = _test_documents()
            results["search"] = _test_search(params)
            results["hybrid-search"] = _test_hybrid_search(params)
            results["chat"] = _test_chat(params)
        else:
            return {"code": 1, "message": f"未知的测试目标: {target}"}
    except Exception as e:
        results["error"] = str(e)

    elapsed = round((time.time() - t0) * 1000)
    return {"code": 0, "message": "success", "data": results, "elapsed_ms": elapsed}


def _test_health() -> dict:
    t0 = time.time()
    try:
        client = get_client()
        ready = client.is_ready()
        return {"status": "ok" if ready else "not_ready", "response_time_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _test_documents() -> dict:
    t0 = time.time()
    try:
        docs = list_documents()
        return {"status": "ok", "count": len(docs), "documents": docs, "response_time_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _test_search(params: dict) -> dict:
    t0 = time.time()
    query = params.get("query", "测试查询")
    top_k = params.get("top_k", 3)
    try:
        results = search_by_vector(query=query, top_k=top_k)
        return {"status": "ok", "query": query, "result_count": len(results), "results": results, "response_time_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _test_hybrid_search(params: dict) -> dict:
    t0 = time.time()
    query = params.get("query", "测试查询")
    top_k = params.get("top_k", 3)
    alpha = params.get("alpha", 0.5)
    try:
        results = hybrid_search(query=query, top_k=top_k, alpha=alpha)
        return {"status": "ok", "query": query, "alpha": alpha, "result_count": len(results), "results": results, "response_time_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _test_chat(params: dict) -> dict:
    t0 = time.time()
    query = params.get("query", "你好")
    model = params.get("model", None)
    try:
        config = get_config()
        top_k = config["search"]["top_k"]
        results = hybrid_search(query=query, top_k=top_k, alpha=1.0)
        context_parts = []
        for r in results:
            filename = r.get("filename", "unknown")
            line_start = r.get("line_start", 0)
            line_end = r.get("line_end", 0)
            context_parts.append(f"[来源: {filename} 行{line_start}-{line_end}]\n{r['text']}")
        context = "\n\n---\n\n".join(context_parts)
        answer = chat(query, context, model=model)
        sources = list({r.get("filename", "unknown") for r in results})
        return {"status": "ok", "query": query, "answer": answer, "sources": sources, "response_time_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
