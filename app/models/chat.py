from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色: user/assistant/system")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    model: str = Field(default="Arch-Agent-3B", description="模型名称，可选: Arch-Agent-3B(本地), xop3qwen1b7(讯飞)")
    messages: list[ChatMessage] = Field(..., description="消息列表")
    conversation_id: Optional[str] = Field(default=None, description="会话ID，为空则创建新会话")
    stream: bool = Field(default=False, description="是否流式响应")
    max_tokens: int = Field(default=1024, description="最大token数")


class ChatChoiceMessage(BaseModel):
    role: str
    content: str


class ChatChoice(BaseModel):
    index: int = 0
    message: ChatChoiceMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ToolCallInfo(BaseModel):
    tool_name: str
    tool_args: dict
    result: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    conversation_id: str
    choices: list[ChatChoice]
    usage: UsageInfo = UsageInfo()
    tool_calls: list[ToolCallInfo] = []


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    provider: str = "local"
    status: str = "available"


class ModelListResponse(BaseModel):
    models: list[ModelInfo]


class ScoreRequest(BaseModel):
    model: str = Field(default="Arch-Agent-3B", description="模型名称")
    prompt: str = Field(..., description="用户的问题")
    response: str = Field(..., description="模型的回复")
    criteria: list[str] = Field(
        default=["相关性", "准确性", "完整性"], description="评估标准"
    )


class ScoreResponse(BaseModel):
    score: int
    breakdown: dict[str, int]
    feedback: str


class ToolParameter(BaseModel):
    name: str
    type: str
    required: bool
    description: str


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: list[ToolParameter]


class ToolListResponse(BaseModel):
    tools: list[ToolInfo]
