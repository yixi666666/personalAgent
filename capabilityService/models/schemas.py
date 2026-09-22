from pydantic import BaseModel, Field
from typing import Optional, Any


class ToolCallRequest(BaseModel):
    name: str = Field(..., description="工具名称")
    arguments: dict = Field(default_factory=dict, description="工具参数")


class ToolCallResponse(BaseModel):
    result: Optional[Any] = None
    error: Optional[dict] = None


class ToolMetadata(BaseModel):
    name: str
    description: str
    parameters: dict = Field(default_factory=dict, description="JSON Schema")


class ToolListResponse(BaseModel):
    tools: list[ToolMetadata]


class SkillMetadata(BaseModel):
    name: str
    description: str
    version: str = ""


class SkillListResponse(BaseModel):
    skills: list[SkillMetadata]


class ErrorResponse(BaseModel):
    code: str
    message: str
