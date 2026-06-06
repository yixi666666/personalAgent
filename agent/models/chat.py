from pydantic import BaseModel, Field
from typing import Optional, Literal


class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色: user/assistant/system/tool")
    content: Optional[str] = Field(default=None, description="消息内容")
    tool_calls: Optional[list[dict]] = Field(default=None, description="工具调用列表")
    tool_call_id: Optional[str] = Field(default=None, description="工具调用ID，role=tool时必填")
    name: Optional[str] = Field(default=None, description="工具名称，role=tool时使用")


class ChatRequest(BaseModel):
    model: str = Field(default="xop3qwen1b7", description="模型名称，可选: Arch-Agent-3B(本地), xop3qwen1b7(星火)")
    prompt: str = Field(..., description="用户输入的提示文本")
    session_id: Optional[str] = Field(default=None, description="会话ID，为空则创建新会话")
    stream: Literal[True] = Field(default=True, description="是否流式响应，强制为True")
    max_tokens: int = Field(default=4096, description="最大token数")
    temperature: Optional[float] = Field(default=None, description="温度参数")


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    provider: str = "local"
    status: str = "available"


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
