from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from agent.models.university import UniversityInfo
from agent.services.university import get_university_by_name

router = APIRouter()

# 校徽图片仅允许从 data/university_logos 目录读取，防止路径穿越
_LOGO_DIR = (Path(__file__).resolve().parents[2] / "data" / "university_logos").resolve()


@router.get("/universities", response_model=UniversityInfo)
def get_university(name: str = Query(..., description="高校全称")):
    """按高校全称查询 universities 表中的完整基础信息"""
    info = get_university_by_name(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"高校不存在: {name}")
    return UniversityInfo(**info)


@router.get("/universities/logo")
def get_university_logo(name: str = Query(..., description="高校全称")):
    """按高校全称返回校徽图片文件（logo_url 为项目根目录下的相对路径）"""
    info = get_university_by_name(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"高校不存在: {name}")
    if not info.get("logo_url"):
        raise HTTPException(status_code=404, detail=f"该校暂无校徽: {name}")

    logo_path = (Path(__file__).resolve().parents[2] / info["logo_url"]).resolve()
    if _LOGO_DIR not in logo_path.parents or not logo_path.is_file():
        raise HTTPException(status_code=404, detail=f"校徽文件不存在: {name}")
    return FileResponse(logo_path, headers={"Cache-Control": "public, max-age=86400"})
