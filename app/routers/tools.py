from fastapi import APIRouter
from app.models.chat import ToolListResponse, ToolInfo, ToolParameter
from app.services.tool_engine import get_tool_engine

router = APIRouter()


@router.get("/tools", response_model=ToolListResponse)
def list_tools():
    tool_engine = get_tool_engine()
    tools = tool_engine.get_all_tools()
    tool_infos = []
    for tool in tools:
        params = [
            ToolParameter(
                name=p["name"],
                type=p["type"],
                required=p["required"],
                description=p["description"],
            )
            for p in tool.parameters
        ]
        tool_infos.append(
            ToolInfo(
                name=tool.name,
                description=tool.description,
                parameters=params,
            )
        )
    return ToolListResponse(tools=tool_infos)
