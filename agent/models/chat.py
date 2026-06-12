from pydantic import BaseModel, Field
from typing import Optional, Literal


class ChatRequest(BaseModel):
    model: str = Field(default="xop3qwen1b7", description="模型名称，可选: deepseek-v4-flash, Arch-Agent-3B(本地), xop3qwen1b7(星火)")
    prompt: str = Field(..., description="用户输入的提示文本")
    session_id: Optional[str] = Field(default=None, description="会话ID，为空则创建新会话")
    stream: Literal[True] = Field(default=True, description="是否流式响应，强制为True")
    max_tokens: int = Field(default=4096, description="最大token数")
    temperature: Optional[float] = Field(default=None, description="温度参数")
    deep_thinking: bool = Field(default=False, description="是否开启深度思考模式（仅DeepSeek模型支持）")


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    provider: str = "local"
    status: str = "available"


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
