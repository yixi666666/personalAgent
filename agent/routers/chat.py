import uuid
import time
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatChoice,
    ChatChoiceMessage,
    UsageInfo,
)
from agent.services.chat_service import get_chat_service

logger = logging.getLogger(__name__)

router = APIRouter()


async def _stream_chat_generator(request: ChatRequest):
    """流式对话生成器：将 ChatService 的事件字典转为 SSE 格式"""
    chat_service = get_chat_service()

    try:
        conversation_id, llm_messages = await chat_service.prepare_conversation(
            conversation_id=request.conversation_id,
            messages=[m.model_dump() for m in request.messages],
            model=request.model,
        )
    except ValueError as e:
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        return

    yield f"data: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"

    async for event in chat_service.stream_chat(
        messages=llm_messages,
        model=request.model,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        conversation_id=conversation_id,
    ):
        event_type = event.get("type")

        if event_type == "delta":
            yield f"data: {json.dumps({'id': f'msg_{uuid.uuid4().hex[:12]}', 'delta': {'content': event['content']}}, ensure_ascii=False)}\n\n"

        elif event_type == "content_replace":
            yield f"data: {json.dumps({'id': f'msg_{uuid.uuid4().hex[:12]}', 'content_replace': {'content': event['content']}}, ensure_ascii=False)}\n\n"

        elif event_type == "tool_calls":
            yield f"data: {json.dumps({'tool_calls': event['tool_calls']}, ensure_ascii=False)}\n\n"

        elif event_type == "error":
            yield f"data: {json.dumps({'error': event['error']}, ensure_ascii=False)}\n\n"

        elif event_type == "finish":
            yield f"data: {json.dumps({'id': f'msg_{uuid.uuid4().hex[:12]}', 'finish_reason': event.get('finish_reason', 'stop')}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"


@router.post("/chat/completions")
async def chat_completions(request: ChatRequest):
    if request.stream:
        return StreamingResponse(
            _stream_chat_generator(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    chat_service = get_chat_service()

    try:
        conversation_id, llm_messages = await chat_service.prepare_conversation(
            conversation_id=request.conversation_id,
            messages=[m.model_dump() for m in request.messages],
            model=request.model,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        result = await chat_service.chat(
            messages=llm_messages,
            model=request.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            conversation_id=conversation_id,
        )
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"对话处理失败: {e}")

    usage_data = result.get("usage", {})

    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=request.model,
        conversation_id=conversation_id,
        choices=[
            ChatChoice(
                index=0,
                message=ChatChoiceMessage(
                    role="assistant",
                    content=result["content"],
                ),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        ),
    )
