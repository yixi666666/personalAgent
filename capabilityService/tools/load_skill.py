import logging

from capabilityService.services.skill_registry import get_skill_registry

logger = logging.getLogger(__name__)


class LoadSkillTool:
    """自研工具：加载指定 skill 的完整 markdown 内容"""

    @property
    def name(self) -> str:
        return "load_skill"

    @property
    def description(self) -> str:
        return (
            "当需要某个 skill 的详细工作指引时调用，"
            "返回该 skill 的完整 markdown 内容供阅读。"
            "调用前请先查看 <available_skills> 标签中列出的可用 skill。"
        )

    @property
    def parameters(self) -> dict:
        skill_names = get_skill_registry().get_skill_names()
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "enum": skill_names,
                    "description": "要加载的 skill 名称",
                }
            },
            "required": ["skill_name"],
        }

    def execute(self, **kwargs) -> dict:
        skill_name = kwargs.get("skill_name", "")
        content = get_skill_registry().get_content(skill_name)
        if content is None:
            return {"error": {"code": "skill_not_found",
                              "message": f"未找到 skill: {skill_name}"}}
        return {"skill_name": skill_name, "content": content}
