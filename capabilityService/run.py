import sys
import os

# 确保大项目根目录在 sys.path 中，使 capabilityService 包可被导入
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.environ["PYTHONPATH"] = _project_root

import uvicorn
from capabilityService.config import get_config


def main():
    config = get_config()
    uvicorn.run(
        "capabilityService.main:app",
        host=config.server_host,
        port=config.server_port,
    )


if __name__ == "__main__":
    main()
