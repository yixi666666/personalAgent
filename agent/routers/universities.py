from fastapi import APIRouter, HTTPException, Query

from agent.models.university import UniversityInfo
from agent.services.university import get_university_by_name

router = APIRouter()


@router.get("/universities", response_model=UniversityInfo)
def get_university(name: str = Query(..., description="高校全称")):
    """按高校全称查询 universities 表中的完整基础信息"""
    info = get_university_by_name(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"高校不存在: {name}")
    return UniversityInfo(**info)
