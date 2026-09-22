import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from capabilityService.models.schemas import (
    ToolCallRequest,
    ToolCallResponse,
    ToolListResponse,
    ToolMetadata,
)
from capabilityService.services.tool_registry import get_tool_registry

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


@router.get("/tools/{name}")
async def get_tool(name: str):
    registry = get_tool_registry()
    tool = registry.get_tool(name)
    if not tool:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "tool_not_found", "message": f"工具不存在: {name}"}},
        )
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
