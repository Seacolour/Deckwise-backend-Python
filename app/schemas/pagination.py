"""Web-compatible pagination contracts with Pydantic validation."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class PageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    current: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=200, alias="pageSize")
    sort_field: str | None = Field(default=None, alias="sortField", max_length=64)
    sort_order: Literal["asc", "desc"] = Field(default="asc", alias="sortOrder")

    @field_validator("sort_order", mode="before")
    @classmethod
    def normalize_sort_order(cls, value: object) -> object:
        return value.lower() if isinstance(value, str) else value

    @property
    def offset(self) -> int:
        return (self.current - 1) * self.page_size


class PageResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    current: int
    page_size: int = Field(alias="pageSize")
    total: int
    has_next: bool = Field(alias="hasNext")
    records: list[T]

    @classmethod
    def of(cls, current: int, page_size: int, total: int, records: list[T] | None) -> "PageResponse[T]":
        safe_current = max(current, 1)
        safe_page_size = max(page_size, 1)
        safe_total = max(total, 0)
        return cls(
            current=safe_current,
            page_size=safe_page_size,
            total=safe_total,
            has_next=safe_current * safe_page_size < safe_total,
            records=records or [],
        )
