from pydantic import BaseModel
from typing import Optional


class SubjectItem(BaseModel):
    """双一流建设学科条目"""
    name: Optional[str] = None              # 官方学科名（名单原始名称）
    code: Optional[str] = None              # 映射学科代码


class DisciplineItem(BaseModel):
    """学科评估上榜学科条目"""
    code: Optional[str] = None              # 学科代码
    name: Optional[str] = None              # 学科名称
    grade: Optional[str] = None             # 评估档位，如 A+ / B


class UniversityRanking(BaseModel):
    """高校排名记录（ranking_record 表中的一行）"""
    source: Optional[str] = None            # 榜单来源：'qs'/'the'/'usnews'/'ruanke'/'xyh'
    year: Optional[int] = None              # 榜单年份
    rank_raw: Optional[str] = None          # 原始名次，保真存储，如 "500+"、"501-510"
    rank_num: Optional[int] = None          # 数字名次
    score: Optional[float] = None           # 总分（各榜单口径不同）
    max_score: Optional[float] = None       # 同榜单同年全部高校的最高分


class DoubleFirstSubject(BaseModel):
    """双一流建设学科记录（double_first_subject 表中的一行，一校一轮一行）"""
    round: Optional[int] = None             # 建设轮次：1=第一轮(2017)，2=第二轮(2022)
    subjects: list[SubjectItem] = []        # 建设学科列表；autonomous=1 时高校自主确定，可能为空
    autonomous: Optional[int] = None        # 是否自主确定建设学科：1=自主，0=官方公布
    note: Optional[str] = None              # 备注


class DisciplineEvaluation(BaseModel):
    """学科评估记录（discipline_evaluation 表中的一行，一校一行）"""
    round: Optional[int] = None             # 轮次：4=第四轮
    disciplines: list[DisciplineItem] = []  # 该校全部上榜学科（档位降序、同档按学科code升序）


class UniversityInfo(BaseModel):
    """高校完整信息（universities 表中的一行 + 实力数据）"""
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
    tags: list[str] = []                        # 荣誉/隶属标签（库中为 JSON 数组字符串）
    master_first: Optional[int] = None          # 一级学科硕士点数
    doctor_first: Optional[int] = None          # 一级学科博士点数
    logo_url: Optional[str] = None              # 校徽图片相对路径（如 data/university_logos/{code}.jpg）
    raw_remark: Optional[str] = None            # 教育部名单原始备注
    rankings: list[UniversityRanking] = []                  # 排名榜单记录
    double_first_subjects: list[DoubleFirstSubject] = []    # 双一流建设学科（按轮次）
    discipline_evaluations: list[DisciplineEvaluation] = [] # 学科评估（按轮次）
    created_time: Optional[int] = None
    updated_time: Optional[int] = None
