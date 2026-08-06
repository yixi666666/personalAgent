import logging
from fastapi import APIRouter

from capabilityService.models.schemas import SkillListResponse, SkillMetadata
from capabilityService.services.skill_registry import get_skill_registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/skills/list", response_model=SkillListResponse)
async def list_skills():
    registry = get_skill_registry()
    skills = registry.list_meta()
    return SkillListResponse(
        skills=[
            SkillMetadata(
                name=s["name"],
                description=s.get("description", ""),
                version=s.get("version", ""),
            )
            for s in skills
        ]
    )
