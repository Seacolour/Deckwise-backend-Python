"""Pagination shape and limits shared with the existing Web client."""

import pytest
from pydantic import ValidationError

from app.schemas.pagination import PageRequest, PageResponse


def test_page_request_and_response_match_web_contract() -> None:
    request = PageRequest.model_validate(
        {"current": 2, "pageSize": 5, "sortField": "updatedAt", "sortOrder": "DESC"}
    )
    page = PageResponse[int].of(request.current, request.page_size, 11, [6, 7, 8, 9, 10])

    assert request.offset == 5
    assert request.sort_order == "desc"
    assert page.model_dump(by_alias=True) == {
        "current": 2, "pageSize": 5, "total": 11,
        "hasNext": True, "records": [6, 7, 8, 9, 10],
    }


@pytest.mark.parametrize("payload", [{"current": 0}, {"pageSize": 201}, {"sortOrder": "sideways"}])
def test_page_request_rejects_invalid_values(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        PageRequest.model_validate(payload)
