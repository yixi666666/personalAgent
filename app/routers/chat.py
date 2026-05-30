import uuid
import time
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.chat import (
    ChatRequest,
    ChatResponse,
    ChatChoice,
    ChatChoiceMessage,
    UsageInfo,
    ToolCallInfo,
)
from app.services.conversation import get_conversation_manager
from app.services.context import get_context_manager
from app.services.tool_engine import get_tool_engine
from app.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _stream_chat_generator(request: ChatRequest):
    conv_manager = get_conversation_manager()
    ctx_manager = get_context_manager()
    tool_engine = get_tool_engine()
    llm_client = get_llm_client()

    conversation_id = request.conversation_id
    if conversation_id:
        if not conv_manager.conversation_exists(conversation_id):
            yield f"data: {json.dumps({'error': f'会话不存在: {conversation_id}'}, ensure_ascii=False)}\n\n"
            return
    else:
        conv = conv_manager.create_conversation()
        conversation_id = conv["conversation_id"]

    new_messages = [{"role": m.role, "content": m.content} for m in request.messages]
    llm_messages = ctx_manager.build_llm_messages(conversation_id, new_messages)

    new_user_messages = [msg for msg in new_messages if msg["role"] == "user"]
    db_history = conv_manager.get_messages(conversation_id) if conversation_id else []
    db_user_count = sum(1 for m in db_history if m["role"] == "user")
    for msg in new_user_messages[db_user_count:]:
        conv_manager.add_message(conversation_id, msg["role"], msg["content"])

    yield f"data: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"

    try:
        prep = tool_engine.prepare_for_streaming(llm_messages, conversation_id)
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        return

    final_messages = prep["messages"]
    tool_call_records = prep["tool_calls"]

    if tool_call_records:
        yield f"data: {json.dumps({'tool_calls': tool_call_records}, ensure_ascii=False)}\n\n"

    msg_id = f"msg_{uuid.uuid4().hex[:12]}"
    full_content = ""

    try:
        for chunk_data in llm_client.chat_stream(
            final_messages,
            model=request.model,
            max_tokens=request.max_tokens,
        ):
            try:
                chunk = json.loads(chunk_data)
                delta_content = (
                    chunk.get("choices", [{}])[0]
                    .get("delta", {})
                    .get("content", "")
                )
                if delta_content:
                    full_content += delta_content
                    yield f"data: {json.dumps({'id': msg_id, 'delta': {'content': delta_content}}, ensure_ascii=False)}\n\n"
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logger.error(f"LLM流式调用失败: {e}")
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        if full_content:
            conv_manager.add_message(conversation_id, "assistant", full_content)
        return

    conv_manager.add_message(conversation_id, "assistant", full_content)

    yield f"data: {json.dumps({'id': msg_id, 'finish_reason': 'stop'}, ensure_ascii=False)}\n\n"
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

    conv_manager = get_conversation_manager()
    ctx_manager = get_context_manager()
    tool_engine = get_tool_engine()

    conversation_id = request.conversation_id
    if conversation_id:
        if not conv_manager.conversation_exists(conversation_id):
            raise HTTPException(status_code=404, detail=f"会话不存在: {conversation_id}")
    else:
        conv = conv_manager.create_conversation()
        conversation_id = conv["conversation_id"]

    new_messages = [{"role": m.role, "content": m.content} for m in request.messages]

    llm_messages = ctx_manager.build_llm_messages(conversation_id, new_messages)

    new_user_messages = [msg for msg in new_messages if msg["role"] == "user"]
    db_history = conv_manager.get_messages(conversation_id) if conversation_id else []
    db_user_count = sum(1 for m in db_history if m["role"] == "user")
    for msg in new_user_messages[db_user_count:]:
        conv_manager.add_message(conversation_id, msg["role"], msg["content"])

    try:
        result = tool_engine.analyze_and_execute(llm_messages, conversation_id)
    except Exception as e:
        logger.error(f"对话处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"对话处理失败: {e}")

    conv_manager.add_message(conversation_id, "assistant", result["content"])

    tool_call_infos = []
    for tc in result.get("tool_calls", []):
        tool_call_infos.append(
            ToolCallInfo(
                tool_name=tc["tool_name"],
                tool_args=tc["tool_args"],
                result=tc.get("result"),
            )
        )

    usage_data = result.get("usage", {})

    return ChatResponse(
        id=f"msg_{uuid.uuid4().hex[:12]}",
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
        tool_calls=tool_call_infos,
    )
