import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_config
from app.database import init_db, close_db
from app.routers import chat, conversations, models, score, tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = get_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format=config.log_format,
    )
    logger = logging.getLogger(__name__)
    logger.info("正在初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")
    logger.info(f"智能聊天Agent系统启动 - 端口: {config.server_port}")
    yield
    logger.info("正在关闭服务...")
    close_db()
    logger.info("服务已关闭")


app = FastAPI(
    title="智能聊天Agent系统",
    description="基于Arch-Agent-3B的智能聊天Agent系统，支持工具调用",
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

app.include_router(chat.router, prefix="/v1", tags=["对话服务"])
app.include_router(conversations.router, prefix="/v1", tags=["会话管理"])
app.include_router(models.router, prefix="/v1", tags=["模型管理"])
app.include_router(score.router, prefix="/v1", tags=["评估服务"])
app.include_router(tools.router, prefix="/v1", tags=["工具管理"])


@app.get("/")
def root():
    return {
        "service": "智能聊天Agent系统",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
