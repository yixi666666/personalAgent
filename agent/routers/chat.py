import uuid
import time
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent.models.chat import ChatRequest
from agent.services.chat_service import get_chat_service
from agent.config import get_config

logger = logging.getLogger(__name__)

router = APIRouter()


async def _stream_chat_generator(request: ChatRequest):
    """流式对话生成器：将 ChatService 的事件字典转为 SSE 格式"""
    chat_service = get_chat_service()
    model = request.model or get_config().default_model

    try:
        session_id, llm_messages, user_msg_id = await chat_service.prepare_session(
            session_id=request.session_id,
            prompt=request.prompt,
            model=model,
        )
    except ValueError as e:
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        return

    yield f"data: {json.dumps({'session_id': session_id}, ensure_ascii=False)}\n\n"

    async for event in chat_service.stream_chat(
        messages=llm_messages,
        model=model,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        session_id=session_id,
        parent_id=user_msg_id,
        deep_thinking=request.deep_thinking,
    ):
        event_type = event.get("type")

        if event_type == "delta":
            yield f"data: {json.dumps({'id': f'msg_{uuid.uuid4().hex[:12]}', 'delta': {'content': event['content']}}, ensure_ascii=False)}\n\n"

        elif event_type == "reasoning_delta":
            yield f"data: {json.dumps({'id': f'msg_{uuid.uuid4().hex[:12]}', 'reasoning_delta': {'content': event['content']}}, ensure_ascii=False)}\n\n"

        elif event_type == "content_replace":
            yield f"data: {json.dumps({'id': f'msg_{uuid.uuid4().hex[:12]}', 'content_replace': {'content': event['content']}}, ensure_ascii=False)}\n\n"

        elif event_type == "tool_calls":
            yield f"data: {json.dumps({'tool_calls': event['tool_calls']}, ensure_ascii=False)}\n\n"

        elif event_type == "tool_results":
            yield f"data: {json.dumps({'tool_results': event['tool_results']}, ensure_ascii=False)}\n\n"

        elif event_type == "error":
            yield f"data: {json.dumps({'error': event['error']}, ensure_ascii=False)}\n\n"

        elif event_type == "finish":
            yield f"data: {json.dumps({'id': f'msg_{uuid.uuid4().hex[:12]}', 'finish_reason': event.get('finish_reason', 'stop')}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    """流式对话接口，强制 stream=True"""
    return StreamingResponse(
        _stream_chat_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
