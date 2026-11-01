"""Web-compatible daily check-in request and response types."""

from pydantic import BaseModel, Field


class CheckinRequest(BaseModel):
    deviceToken: str | None = Field(default=None, max_length=512)
    deviceType: str | None = Field(default=None, max_length=32)
    environment: str | None = Field(default=None, max_length=32)
    timeZone: str | None = Field(default=None, max_length=80)
    locale: str | None = Field(default=None, max_length=35)
    country: str | None = Field(default=None, max_length=3)


class CheckinStatusDTO(BaseModel):
    streakCount: int
    longestStreak: int
    lastCheckinDate: str | None


class CheckinResultDTO(BaseModel):
    checkedIn: bool
    rewardPoints: int
    streakAfter: int
    longestStreak: int
    date: str
