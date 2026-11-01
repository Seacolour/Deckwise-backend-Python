"""Web-compatible user login DTOs."""

from pydantic import BaseModel, EmailStr, Field


class EmailCodeRequest(BaseModel):
    email: EmailStr


class LoginRequest(EmailCodeRequest):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    locale: str | None = Field(default=None, max_length=35)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    time_zone: str | None = Field(default=None, alias="timeZone", max_length=80)


class UserDTO(BaseModel):
    id: str
    email: str
    role: str
    emailVerified: bool
    name: str | None
    avatarUrl: str | None
    signUpProvider: str
    lastLoginAt: str | None
