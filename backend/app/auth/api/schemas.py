from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
    roles: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105


class UserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str
    email: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
