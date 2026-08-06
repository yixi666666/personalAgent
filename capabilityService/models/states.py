from enum import Enum


class ToolState(str, Enum):
    """工具状态枚举"""
    UNINITIALIZED = "uninitialized"  # 未初始化
    STARTING = "starting"  # 正在启动
    START_FAILED = "start_failed"  # 启动失败
    RUNNING = "running"  # 正常运行
    UNHEALTHY = "unhealthy"  # 健康检查失败
    STOPPING = "stopping"  # 正在停止
    STOPPED = "stopped"  # 已停止
    STOP_FAILED = "stop_failed"  # 停止失败
    FATAL_ERROR = "fatal_error"  # 致命错误，不可恢复

    @property
    def label(self) -> str:
        mapping = {
            self.UNINITIALIZED: "未初始化",
            self.STARTING: "启动中",
            self.START_FAILED: "启动失败",
            self.RUNNING: "正常运行",
            self.UNHEALTHY: "运行异常（健康检测失败）",
            self.STOPPING: "停止中",
            self.STOPPED: "已停止",
            self.STOP_FAILED: "停止失败",
            self.FATAL_ERROR: "致命错误",
        }
        return mapping[self]


class McpServerState(Enum):
    """MCP服务器级别状态枚举"""
    DISCONNECTED = "disconnected"   # 未连接
    CONNECTING = "connecting"       # 正在连接/握手
    CONNECTED = "connected"         # 连接正常
    ERROR = "error"                 # 连接异常（如进程退出、网络断开）
    SHUTTING_DOWN = "shutting_down" # 正在关闭
    SHUTDOWN = "shutdown"           # 已关闭
