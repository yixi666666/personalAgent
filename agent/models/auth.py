from typing import Optional

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    display_name: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    """忘记密码：账号+邮箱匹配后直接设置新密码并登录"""

    username: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class UpgradeRequest(BaseModel):
    """游客账号转正：username/password 必填，email/display_name 可选"""

    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    email: Optional[str] = None
    display_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    role: str
    status: str
    last_login_time: Optional[int] = None
    last_login_ip: Optional[str] = None
    created_time: Optional[int] = None
    updated_time: Optional[int] = None
