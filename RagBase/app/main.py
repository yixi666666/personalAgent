from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routes import router
from app.vectorstore import get_embeddings
from app.weaviate_client import close_client, init_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务启动时初始化 Embedding 模型和 Weaviate 客户端。"""
    # 初始化 Embedding 模型（加载 bge-small-zh）
    get_embeddings()
    # 初始化 Weaviate 客户端并创建 Chunk collection（如果不存在）
    init_client()
    yield
    # 关闭 Weaviate 客户端连接
    close_client()


app = FastAPI(title="RagBase", version="2.0.0", lifespan=lifespan)
app.include_router(router)

# 挂载静态文件
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/")
def root():
    return RedirectResponse(url="/index.html")


app.mount("/", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn

    from app.config import get_config

    config = get_config()
    uvicorn.run(
        "app.main:app",
        host=config["server"]["host"],
        port=config["server"]["port"],
    )
