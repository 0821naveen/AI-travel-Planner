from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterUserRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserProfileResponse(BaseModel):
    user_id: str
    full_name: str
    email: EmailStr
    role: str
    is_superuser: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse
