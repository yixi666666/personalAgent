import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class DateInfoTool:
    """自研工具：获取当前日期和时间信息"""

    @property
    def name(self) -> str:
        return "date_info"

    @property
    def description(self) -> str:
        return "获取当前日期和时间信息"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def execute(self, **kwargs) -> str:
        utc_now = datetime.now(timezone.utc)
        cst_now = utc_now + timedelta(hours=8)
        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return (
            f"当前日期时间: {cst_now.strftime('%Y年%m月%d日 %H:%M:%S')}\n"
            f"星期: {weekday_names[cst_now.weekday()]}\n"
            f"时区: Asia/Shanghai (UTC+8)"
        )
