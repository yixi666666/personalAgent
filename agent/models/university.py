from pydantic import BaseModel
from typing import Optional


class UniversityInfo(BaseModel):
    """高校基础信息（universities 表中的一行）"""
    id: str
    code: Optional[str] = None                  # 10位学校标识码
    name: Optional[str] = None                  # 高校全称
    aliases: list[str] = []                     # 别名列表（库中为 JSON 数组字符串）
    official_website: Optional[str] = None      # 官方网站
    category: Optional[str] = None              # ordinary | adult
    competent_department: Optional[str] = None  # 主管部门
    province: Optional[str] = None              # 所在省
    city: Optional[str] = None                  # 所在市
    edu_level: Optional[str] = None             # 办学层次：本科 / 专科
    school_nature: Optional[str] = None         # 办学性质：公办 / 民办
    raw_remark: Optional[str] = None            # 教育部名单原始备注
    created_time: Optional[int] = None
    updated_time: Optional[int] = None
