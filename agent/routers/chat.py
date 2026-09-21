import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from agent.models.chat import ChatRequest
from agent.services.chat_service import get_chat_service
from agent.services.stream_bus import DONE, get_stream_bus


logger = logging.getLogger(__name__)

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _format_sse_event(event: dict) -> str | None:
    event_type = event.get("type")

    if event_type == "session":
        payload = {"session_id": event["session_id"]}
        if event.get("session") is not None:
            payload["session"] = event["session"]
    elif event_type == "delta":
        payload = {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "delta": {"content": event["content"]},
        }
    elif event_type == "reasoning_delta":
        payload = {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "reasoning_delta": {"content": event["content"]},
        }
    elif event_type == "content_replace":
        payload = {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "content_replace": {"content": event["content"]},
        }
    elif event_type == "tool_calls":
        payload = {"tool_calls": event["tool_calls"]}
    elif event_type == "tool_results":
        payload = {"tool_results": event["tool_results"]}
    elif event_type == "error":
        payload = {"error": event["error"]}
    elif event_type == "finish":
        payload = {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "finish_reason": event.get("finish_reason", "stop"),
        }
    else:
        return None

    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _error_generator(message: str) -> AsyncGenerator[str, None]:
    yield _format_sse_event({"type": "error", "error": message})
    yield "data: [DONE]\n\n"


def _error_response(message: str) -> StreamingResponse:
    return StreamingResponse(
        _error_generator(message),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _subscribe_generator(stream_id: str) -> AsyncGenerator[str, None]:
    bus = get_stream_bus()
    subscription = bus.subscribe(stream_id)
    if subscription is None:
        yield _format_sse_event({"type": "error", "error": "对话流不存在或已过期"})
        yield "data: [DONE]\n\n"
        return

    buffered_events, queue = subscription
    try:
        for event in buffered_events:
            line = _format_sse_event(event)
            if line is not None:
                yield line

        while True:
            event = await queue.get()
            if event is DONE:
                break
            line = _format_sse_event(event)
            if line is not None:
                yield line

        yield "data: [DONE]\n\n"
    finally:
        bus.unsubscribe(stream_id, queue)


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    """启动独立后台对话管线，并通过 SSE 订阅处理事件。"""
    bus = get_stream_bus()
    if request.session_id and bus.active_stream_for_session(request.session_id):
        return _error_response("当前会话正在处理上一条消息，请等待完成后再发送")

    chat_service = get_chat_service()
    try:
        session_id, user_msg_id, created_session = await chat_service.prepare_session(
            session_id=request.session_id,
            prompt=request.prompt,
            model=request.model,
        )
    except Exception as exc:
        logger.exception("准备对话会话失败")
        return _error_response(str(exc))

    async def pipeline() -> AsyncGenerator[dict, None]:
        session_event = {"type": "session", "session_id": session_id}
        if created_session:
            session_event["session"] = created_session
        yield session_event

        async for event in chat_service.stream_chat(
            session_id=session_id,
            user_query=request.prompt,
            user_msg_id=user_msg_id,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            deep_thinking=request.deep_thinking,
        ):
            yield event

    bus.start_stream(
        session_id=session_id,
        stream_id=user_msg_id,
        pipeline=pipeline(),
    )
    return StreamingResponse(
        _subscribe_generator(user_msg_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/chat/streams/active")
async def get_active_stream(session_id: str = Query(...)):
    stream = get_stream_bus().active_stream_for_session(session_id)
    if stream is None:
        raise HTTPException(status_code=404, detail="当前会话没有活跃对话流")
    return {"stream_id": stream.stream_id, "session_id": stream.session_id}


@router.get("/chat/stream/{stream_id}")
async def attach_chat_stream(stream_id: str):
    if get_stream_bus().get(stream_id) is None:
        raise HTTPException(status_code=404, detail="对话流不存在或已过期")
    return StreamingResponse(
        _subscribe_generator(stream_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
