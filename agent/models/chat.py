from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色: user/assistant/system/tool")
    content: Optional[str] = Field(default=None, description="消息内容")
    tool_calls: Optional[list[dict]] = Field(default=None, description="工具调用列表")
    tool_call_id: Optional[str] = Field(default=None, description="工具调用ID，role=tool时必填")
    name: Optional[str] = Field(default=None, description="工具名称，role=tool时使用")


class ChatRequest(BaseModel):
    model: str = Field(default="xop3qwen1b7", description="模型名称，可选: Arch-Agent-3B(本地), xop3qwen1b7(星火)")
    messages: list[ChatMessage] = Field(..., description="消息列表")
    conversation_id: Optional[str] = Field(default=None, description="会话ID，为空则创建新会话")
    stream: bool = Field(default=False, description="是否流式响应")
    max_tokens: int = Field(default=2048, description="最大token数")
    temperature: Optional[float] = Field(default=None, description="温度参数")


class ChatChoiceMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    conversation_id: str
    choices: list[ChatChoice]
    usage: UsageInfo = UsageInfo()


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    provider: str = "local"
    status: str = "available"


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
