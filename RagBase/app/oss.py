"""对象存储抽象层与本地实现。

后续引入真 OSS（阿里云/腾讯云/MinIO）时，只需新增实现类替换 LocalObjectStorage 即可。
"""
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_config


class ObjectStorage(ABC):
    """对象存储抽象接口。"""

    @abstractmethod
    def put(self, oss_key: str, content: bytes) -> None:
        """上传文件内容。"""

    @abstractmethod
    def get(self, oss_key: str) -> bytes:
        """下载文件内容。不存在时抛出 FileNotFoundError。"""

    @abstractmethod
    def head(self, oss_key: str) -> dict:
        """检查文件元信息，返回 {"exists": bool, "size": int}。"""

    @abstractmethod
    def exists(self, oss_key: str) -> bool:
        """文件是否存在。"""

    @abstractmethod
    def delete(self, oss_key: str) -> None:
        """删除文件（流程中 OSS 不删，但保留接口）。"""


class LocalObjectStorage(ObjectStorage):
    """基于本地文件系统的对象存储实现（模拟 OSS）。

    oss_key 直接映射为相对于 root 的文件路径。
    例如 oss_key="uploads/default/sessions/conv_123/uuid.txt"
      → {root}/uploads/default/sessions/conv_123/uuid.txt
    """

    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, oss_key: str) -> Path:
        """将 oss_key 解析为本地文件路径，防止路径穿越。"""
        path = (self.root / oss_key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError(f"非法的 oss_key，路径越界: {oss_key}")
        return path

    def put(self, oss_key: str, content: bytes) -> None:
        path = self._resolve_path(oss_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get(self, oss_key: str) -> bytes:
        path = self._resolve_path(oss_key)
        if not path.exists():
            raise FileNotFoundError(f"OSS 对象不存在: {oss_key}")
        return path.read_bytes()

    def head(self, oss_key: str) -> dict:
        path = self._resolve_path(oss_key)
        if not path.exists():
            return {"exists": False, "size": 0}
        return {"exists": True, "size": path.stat().st_size}

    def exists(self, oss_key: str) -> bool:
        return self._resolve_path(oss_key).exists()

    def delete(self, oss_key: str) -> None:
        path = self._resolve_path(oss_key)
        if path.exists():
            path.unlink()


# ---------- 单例 ----------

_storage: ObjectStorage | None = None


def get_storage() -> ObjectStorage:
    """获取对象存储实例（单例）。"""
    global _storage
    if _storage is None:
        config = get_config()
        root = config["local_oss"]["root"]
        _storage = LocalObjectStorage(root=root)
    return _storage
