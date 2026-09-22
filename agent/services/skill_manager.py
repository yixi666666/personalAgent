import asyncio
import logging
from typing import Optional

import httpx

from agent.config import get_config

logger = logging.getLogger(__name__)


class SkillManager:
    """从 capabilityService 获取 skill 元信息列表，缓存供 PromptBuilder 使用"""

    def __init__(self):
        config = get_config()
        self._capabilityservice_url = config.capabilityservice_url
        self._http_client: Optional[httpx.AsyncClient] = None
        self._skills: list[dict] = []
        self._refresh_task: Optional[asyncio.Task] = None
        self._refresh_interval = config.capabilityservice_refresh_interval

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def refresh_skills(self):
        """调用 GET http://localhost:8003/skills/list 刷新 skill 元信息缓存"""
        try:
            client = await self._get_http_client()
            url = f"{self._capabilityservice_url}/skills/list"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            skills_list = data.get("skills", [])
            new_skills = []
            for skill in skills_list:
                name = skill.get("name", "")
                if name:
                    new_skills.append({
                        "name": name,
                        "description": skill.get("description", ""),
                        "version": skill.get("version", ""),
                    })
            self._skills = new_skills
            logger.info(
                f"Skill 元信息已刷新，共 {len(self._skills)} 个 skill: "
                f"{[s['name'] for s in self._skills]}"
            )
        except httpx.HTTPStatusError as e:
            logger.error(f"获取 skill 列表失败: HTTP {e.response.status_code}")
            raise
        except httpx.RequestError as e:
            logger.error(f"获取 skill 列表失败: {e}")
            raise

    def start_refresh_task(self):
        """启动定时刷新 skill 列表的后台任务"""
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(self._periodic_refresh())

    def stop_refresh_task(self):
        """停止定时刷新任务"""
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()

    async def _periodic_refresh(self):
        """定期刷新 skill 列表"""
        while True:
            try:
                await asyncio.sleep(self._refresh_interval)
                await self.refresh_skills()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"定时刷新 skill 列表失败: {e}")

    def get_skills_meta(self) -> list[dict]:
        """返回当前缓存的 skill 元信息列表。

        如果为空，调用方应先触发一次 refresh。
        """
        return self._skills


# ==================== 单例 ====================

_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager
