"""The response envelope consumed by the existing Next.js frontend."""

from typing import Generic, TypeVar

from pydantic import BaseModel

from app.core.error_codes import ErrorCode

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    code: int
    data: T | None
    message: str


def ok(data: object) -> dict[str, object]:
    return BaseResponse[object](code=ErrorCode.SUCCESS, data=data, message="ok").model_dump(mode="json")
