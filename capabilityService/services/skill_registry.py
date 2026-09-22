import logging
import os
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_SKILLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills",
)

_SKILL_FILENAME = "SKILL.md"


class SkillRegistry:
    """扫描、解析、缓存所有 skill。

    启动时扫描 capabilityService/skills/*/SKILL.md，
    解析 YAML front matter 提取 name/description/version，
    校验目录名与 name 字段一致，校验无重名 skill。
    """

    def __init__(self):
        self._skills: dict[str, dict] = {}
        # {skill_name: {"meta": {...}, "content": "..."}}

    def initialize(self) -> None:
        """启动时扫描 skills 目录，解析并缓存所有 skill。"""
        self._skills.clear()

        if not os.path.isdir(_SKILLS_DIR):
            logger.warning(f"skills 目录不存在: {_SKILLS_DIR}")
            return

        for entry in sorted(os.listdir(_SKILLS_DIR)):
            skill_dir = os.path.join(_SKILLS_DIR, entry)
            if not os.path.isdir(skill_dir):
                continue

            skill_file = os.path.join(skill_dir, _SKILL_FILENAME)
            if not os.path.isfile(skill_file):
                logger.debug(f"目录 {entry} 下无 {_SKILL_FILENAME}，跳过")
                continue

            try:
                meta, content = self._parse_skill_file(skill_file)
            except Exception as e:
                logger.error(f"解析 skill 失败 ({skill_file}): {e}")
                continue

            name = meta.get("name", "")
            if not name:
                logger.error(f"skill 文件 {skill_file} 的 front matter 缺少 name 字段")
                continue

            if name != entry:
                logger.error(
                    f"skill 目录名 '{entry}' 与 front matter name '{name}' 不一致，跳过"
                )
                continue

            if name in self._skills:
                logger.error(f"skill 重名: '{name}'，跳过后续同名 skill")
                continue

            self._skills[name] = {"meta": meta, "content": content}
            logger.info(f"已加载 skill: {name}")

        logger.info(f"Skill 注册完成，共 {len(self._skills)} 个 skill: {list(self._skills.keys())}")

    @staticmethod
    def _parse_skill_file(file_path: str) -> tuple[dict, str]:
        """解析 YAML front matter + markdown 正文。

        返回 (meta_dict, content_str)。
        """
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()

        if not raw.startswith("---"):
            raise ValueError(f"文件不以 YAML front matter 开头: {file_path}")

        # 分割 front matter 和正文
        parts = raw.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"front matter 格式不正确: {file_path}")

        yaml_block = parts[1]
        content = parts[2].lstrip("\n")

        meta = yaml.safe_load(yaml_block)
        if not isinstance(meta, dict):
            raise ValueError(f"front matter 不是有效的 YAML 字典: {file_path}")

        return meta, content

    def list_meta(self) -> list[dict]:
        """返回所有 skill 的元信息列表。"""
        result = []
        for skill_data in self._skills.values():
            meta = skill_data["meta"]
            result.append({
                "name": meta.get("name", ""),
                "description": meta.get("description", ""),
                "version": meta.get("version", ""),
            })
        return result

    def get_skill_names(self) -> list[str]:
        """返回所有 skill 的 name 列表，供 LoadSkillTool 生成 enum。"""
        return list(self._skills.keys())

    def get_content(self, name: str) -> Optional[str]:
        """返回指定 skill 的完整 markdown 正文，找不到返回 None。"""
        skill_data = self._skills.get(name)
        if skill_data is None:
            return None
        return skill_data["content"]


# ==================== 单例 ====================

_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry
