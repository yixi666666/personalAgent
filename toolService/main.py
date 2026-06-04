import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from toolservice.config import get_config
from toolservice.routers import tools
from toolservice.services.tool_registry import get_tool_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format=config.log_format,
    )
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
def health_check():
    return {"status": "healthy"}
