import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from agent.config import get_config
from agent.database import get_db, close_db
from agent.routers import chat, sessions, models
from agent.services.tool_manager import get_tool_manager
from agent.services.skill_manager import get_skill_manager
from agent.services.llm_client import get_llm_client


class FixedWidthFormatter(logging.Formatter):
    """自定义日志格式器：将 name 字段截断/补齐到固定宽度"""
    def __init__(self, fmt=None, datefmt=None, style='%', name_width=20):
        super().__init__(fmt, datefmt, style)
        self.name_width = name_width

    def format(self, record):
        record.name = record.name[:self.name_width].ljust(self.name_width)
        return super().format(record)


# 在模块导入阶段就配置日志，确保所有logger都能输出DEBUG级别
_config = get_config()
logging.basicConfig(
    level=getattr(logging, _config.log_level, logging.INFO),
    format=_config.log_format,
    force=True,
)
# 替换所有 handler 的 formatter 为 FixedWidthFormatter
_name_width = 20
for handler in logging.getLogger().handlers:
    handler.setFormatter(FixedWidthFormatter(_config.log_format, name_width=_name_width))
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    # uvicorn reload 模式会覆盖 logging.basicConfig，这里重新配置
    log_level = getattr(logging, config.log_level, logging.INFO)
    logging.getLogger("agent").setLevel(log_level)
    # 确保 agent 下所有 logger 的 handler 级别和格式也正确
    for handler in logging.getLogger().handlers:
        if handler.level > log_level:
            handler.setLevel(log_level)
        handler.setFormatter(FixedWidthFormatter(config.log_format, name_width=_name_width))

    logger = logging.getLogger(__name__)
    logger.info("正在检查数据库...")
    get_db()
    logger.info("数据库检查完成")

    logger.info("正在从capabilityService获取工具列表...")
    tool_manager = get_tool_manager()
    try:
        await tool_manager.refresh_tools()
        logger.info(f"工具列表获取完成，共 {len(tool_manager._tools)} 个工具")
    except Exception as e:
        logger.warning(f"从capabilityService获取工具列表失败: {e}，将在后台重试")

    tool_manager.start_refresh_task()

    logger.info("正在从capabilityService获取skill列表...")
    skill_manager = get_skill_manager()
    try:
        await skill_manager.refresh_skills()
        logger.info(f"Skill 列表获取完成，共 {len(skill_manager._skills)} 个 skill")
    except Exception as e:
        logger.warning(f"从capabilityService获取skill列表失败: {e}，将在后台重试")

    skill_manager.start_refresh_task()

    logger.info(f"智能聊天Agent系统启动 - 端口: {config.server_port}")
    yield

    logger.info("正在关闭服务...")
    tool_manager.stop_refresh_task()
    skill_manager.stop_refresh_task()
    await skill_manager.close()
    llm_client = get_llm_client()
    await llm_client.close()
    close_db()
    logger.info("服务已关闭")


app = FastAPI(
    title="智能聊天Agent系统",
    description="基于大语言模型的智能聊天Agent系统，支持工具调用",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/v1", tags=["对话服务"])
app.include_router(sessions.router, prefix="/v1", tags=["会话管理"])
app.include_router(models.router, prefix="/v1", tags=["模型管理"])


@app.get("/")
def root():
    return {
        "service": "智能聊天Agent系统",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/v1/tools")
async def list_tools():
    tool_manager = get_tool_manager()
    tools_list = []
    for name, tool_info in tool_manager._tools.items():
        tools_list.append({
            "name": name,
            "description": tool_info.get("description", ""),
            "parameters": tool_info.get("parameters", {}),
        })
    return {"tools": tools_list}
