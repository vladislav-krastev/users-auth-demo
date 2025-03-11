from typing import TypedDict

import pydantic
import pydantic_settings


class HTTPExceptionResponse(TypedDict):
    """Model for a raised `fastapi.HTTPException`."""

    detail: str


class Item[T: pydantic.BaseModel | pydantic_settings.BaseSettings](TypedDict):
    """Response body for a single item."""

    data: T


class ItemPaginated[T: pydantic.BaseModel](TypedDict):
    """Response body for a page from a list of items."""

    count: int
    next: str | None
    data: list[T]


class PaginationOffsetLmitRequest(pydantic.BaseModel):
    """Request query params for getting a page from a list of items."""

    offset: int = pydantic.Field(default=0, ge=0)
    limit: int = pydantic.Field(default=10, ge=1, le=100)
