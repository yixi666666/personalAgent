import logging
from datetime import datetime
from app.tools.base import BaseTool

logger = logging.getLogger(__name__)


class DateInfo(BaseTool):
    @property
    def name(self) -> str:
        return "DateInfo"

    @property
    def description(self) -> str:
        return "获取当前日期和时间信息"

    @property
    def parameters(self) -> list[dict]:
        return []

    def execute(self, **kwargs) -> str:
        now = datetime.now()
        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return (
            f"当前日期时间: {now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
            f"星期: {weekday_names[now.weekday()]}\n"
            f"时区: Asia/Shanghai (UTC+8)"
        )
