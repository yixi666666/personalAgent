import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from toolService.config import get_config
from toolService.routers import tools
from toolService.services.tool_registry import get_tool_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    log_level = getattr(logging, config.log_level, logging.INFO)
    log_formatter = logging.Formatter(config.log_format)

    # 直接设置 root logger 级别和 handler（basicConfig 在 uvicorn 已配置后无效）
    # uvicorn 只在 uvicorn/uvicorn.access logger 上加 handler，root logger 没有 handler
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(log_formatter)
        handler.setLevel(log_level)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(log_formatter)
            handler.setLevel(log_level)

    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logger = logging.getLogger(__name__)

    logger.info("正在初始化工具注册表...")
    registry = get_tool_registry()
    try:
        await registry.initialize()
        logger.info(f"工具注册完成，共 {len(registry._tools)} 个工具")
    except Exception as e:
        logger.warning(f"工具注册初始化失败: {e}，将在后台重试")

    logger.info(f"工具服务启动 - 端口: {config.server_port}")
    yield

    logger.info("正在关闭服务...")
    await registry.shutdown()
    logger.info("服务已关闭")


app = FastAPI(
    title="工具服务 (ToolService)",
    description="统一工具管理服务，支持自研工具、本地MCP工具和远程MCP工具",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools.router, tags=["工具服务"])


@app.get("/")
def root():
    return {
        "service": "工具服务 (ToolService)",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    registry = get_tool_registry()
    tool_states = await registry.health_check_all()
    unhealthy = [name for name, state in tool_states.items() if state != "running"]
    return {
        "status": "healthy" if not unhealthy else "degraded",
        "tools": tool_states,
    }
