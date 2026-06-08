from fastapi import APIRouter, Body, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel
import openai
import time

from app.config import get_config, get_upload_token
from app.document import delete_document, process_upload
from app.llm import chat
from app.vectorstore import list_documents, search_documents

router = APIRouter()


# ---------- /health ----------
@router.get("/health")
def health_check():
    return {"status": "ok"}


# ---------- /v1/upload ----------
@router.post("/v1/upload")
async def upload_document(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    # 权限校验
    if authorization is None:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    try:
        expected_token = get_upload_token()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    if token != expected_token:
        raise HTTPException(status_code=403, detail="无效的 API Token")

    content = await file.read()
    filename = file.filename
    try:
        result = process_upload(filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"code": 0, "message": "success", "data": result}


# ---------- /v1/documents ----------
@router.get("/v1/documents")
def get_documents():
    docs = list_documents()
    return {"code": 0, "message": "success", "data": docs}


# ---------- /v1/documents DELETE ----------
@router.delete("/v1/documents")
def delete_documents(filename: str = Query(..., description="要删除的文件名")):
    result = delete_document(filename)
    return {"code": 0, "message": "success", "data": result}


# ---------- /v1/search ----------
class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/v1/search")
def search(req: SearchRequest):
    config = get_config()
    top_k = req.top_k or config["search"]["top_k"]
    score_threshold = config["search"].get("score_threshold")
    results = search_documents(req.query, top_k=top_k, score_threshold=score_threshold)
    return {"code": 0, "message": "success", "data": results}


# ---------- /v1/chat ----------
class ChatRequest(BaseModel):
    query: str
    model: str | None = None
    top_k: int = 5


@router.post("/v1/chat")
def chat_endpoint(req: ChatRequest):
    config = get_config()
    top_k = req.top_k or config["search"]["top_k"]
    score_threshold = config["search"].get("score_threshold")

    # 检索相关文档
    results = search_documents(req.query, top_k=top_k, score_threshold=score_threshold)

    # 构建上下文
    context_parts = []
    for r in results:
        filename = r["metadata"].get("filename", "unknown")
        context_parts.append(f"[来源: {filename}]\n{r['content']}")
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

    sources = list({r["metadata"].get("filename", "unknown") for r in results})

    return {
        "code": 0,
        "message": "success",
        "data": {
            "answer": answer,
            "sources": sources,
        },
    }


# ---------- /v1/test ----------
@router.post("/v1/test")
def test_endpoint(req: dict = Body(default={})):
    """通用接口测试端点，根据 target 调用对应接口并返回结果"""
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
        elif target == "chat":
            results["chat"] = _test_chat(params)
        elif target == "all":
            results["health"] = _test_health()
            results["documents"] = _test_documents()
            results["search"] = _test_search(params)
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
        return {"status": "ok", "response_time_ms": round((time.time() - t0) * 1000)}
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
        config = get_config()
        score_threshold = config["search"].get("score_threshold")
        results = search_documents(query, top_k=top_k, score_threshold=score_threshold)
        return {"status": "ok", "query": query, "result_count": len(results), "results": results, "response_time_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _test_chat(params: dict) -> dict:
    t0 = time.time()
    query = params.get("query", "你好")
    model = params.get("model", None)
    try:
        config = get_config()
        top_k = config["search"]["top_k"]
        score_threshold = config["search"].get("score_threshold")
        results = search_documents(query, top_k=top_k, score_threshold=score_threshold)
        context_parts = []
        for r in results:
            filename = r["metadata"].get("filename", "unknown")
            context_parts.append(f"[来源: {filename}]\n{r['content']}")
        context = "\n\n---\n\n".join(context_parts)
        answer = chat(query, context, model=model)
        sources = list({r["metadata"].get("filename", "unknown") for r in results})
        return {"status": "ok", "query": query, "answer": answer, "sources": sources, "response_time_ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"status": "error", "error": str(e)}
