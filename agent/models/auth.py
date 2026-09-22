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
