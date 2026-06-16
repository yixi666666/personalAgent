from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routes import router
from app.vectorstore import get_embeddings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务启动时初始化 Embedding 模型，立即检测 GPU 并加载"""
    get_embeddings()
    yield


app = FastAPI(title="RagBase", version="1.0.0", lifespan=lifespan)
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
