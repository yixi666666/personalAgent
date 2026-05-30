import uvicorn
from app.config import get_config


def main():
    config = get_config()
    uvicorn.run(
        "app.main:app",
        host=config.server_host,
        port=config.server_port,
        reload=config.server_reload,
    )


if __name__ == "__main__":
    main()
