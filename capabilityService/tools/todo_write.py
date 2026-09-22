import json
import logging

logger = logging.getLogger(__name__)

VALID_STATUSES = {"pending", "in_progress", "completed"}


class TodoWriteTool:
    """自研工具：管理任务计划（todo list），覆盖式更新"""

    @property
    def name(self) -> str:
        return "todo_write"

    @property
    def description(self) -> str:
        return (
            "管理当前会话的任务计划，用于规划和跟踪多步骤任务的执行进度。\n"
            "使用规则：\n"
            "1. 当用户请求涉及多个步骤时，先调用本工具创建任务计划（第一步设为 in_progress，其余设为 pending）。\n"
            "2. 每完成一个步骤后，调用本工具更新：已完成的步骤设为 completed 并填入 result 摘要，下一步设为 in_progress。\n"
            "3. 每次调用必须传入完整的 todos 数组（覆盖式更新），不可只传增量。\n"
            "4. 当所有步骤都 completed 后，正常回复用户最终结果，无需再调用本工具。\n"
            "5. 单步骤任务无需使用本工具。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "完整的任务列表，每次调用传入全部 todo 项",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "任务步骤的简要描述",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "任务状态：pending=待执行, in_progress=执行中, completed=已完成",
                            },
                        },
                        "required": ["action", "status"],
                    },
                }
            },
            "required": ["todos"],
        }

    def execute(self, **kwargs) -> str:
        todos = kwargs.get("todos")
        if not todos or not isinstance(todos, list):
            return "错误：todos 不能为空且必须是数组"

        # 校验每个 todo 项
        for i, todo in enumerate(todos):
            if not isinstance(todo, dict):
                return f"错误：第 {i+1} 个 todo 不是有效对象"
            action = todo.get("action")
            if not action or not isinstance(action, str) or not action.strip():
                return f"错误：第 {i+1} 个 todo 的 action 不能为空"
            status = todo.get("status")
            if status not in VALID_STATUSES:
                return f"错误：第 {i+1} 个 todo 的 status '{status}' 不合法，允许值: {sorted(VALID_STATUSES)}"

        # 统计回执
        status_counts = {"pending": 0, "in_progress": 0, "completed": 0}
        for todo in todos:
            status_counts[todo["status"]] += 1

        # 构建摘要，按状态分组，换行分隔
        parts = []
        for status, label in [("in_progress", "in_progress"), ("pending", "pending"), ("completed", "completed")]:
            count = status_counts[status]
            if count > 0:
                actions = [t["action"] for t in todos if t["status"] == status]
                parts.append(f"{count} {label} ({' || '.join(actions)})")

        receipt = "\n".join(parts) if parts else "0 todos"
        logger.info(f"todo_write called: {receipt}")
        return receipt
