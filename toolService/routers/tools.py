import logging
from fastapi import APIRouter, HTTPException
from toolservice.models.schemas import (
    ToolCallRequest,
    ToolCallResponse,
    ToolListResponse,
    ToolMetadata,
    ErrorResponse,
)
from toolservice.services.tool_registry import get_tool_registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tools/list", response_model=ToolListResponse)
async def list_tools():
    registry = get_tool_registry()
    tools = registry.get_all_tools()
    return ToolListResponse(
        tools=[
            ToolMetadata(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            for t in tools
        ]
    )


@router.get("/tools/{name}", response_model=ToolMetadata)
async def get_tool(name: str):
    registry = get_tool_registry()
    tool = registry.get_tool(name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具不存在: {name}")
    return ToolMetadata(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters,
    )


@router.post("/tools/call", response_model=ToolCallResponse)
async def call_tool(request: ToolCallRequest):
    registry = get_tool_registry()
    result = await registry.execute_tool(request.name, request.arguments)
    if isinstance(result, dict) and "error" in result:
        return ToolCallResponse(error=result["error"])
    return ToolCallResponse(result=result)
