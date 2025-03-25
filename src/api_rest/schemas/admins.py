import typing
import uuid
from datetime import datetime

import pydantic

from config import AppConfig
from utils import validators


class AdminShortResponse(pydantic.BaseModel):
    """Response body containing the short details of an ADMIN `User`."""

    is_admin: typing.Literal[True]
    id: uuid.UUID
    username: str
    created_at: datetime
    # logins_from: list[typing.Any]

    @pydantic.field_serializer("created_at", when_used="json")
    def _serialize_dates(self, v: datetime) -> str:
        return str(v.replace(microsecond=0))


class AdminCreateRequest(pydantic.BaseModel):
    """Request body for creating a new ADMIN `User`."""

    username: str = pydantic.Field(
        min_length=5,
        max_length=20,
    )
    password: str = pydantic.Field(
        min_length=AppConfig.LOCAL_AUTH.PASSWORD.LENGTH_MIN,
        max_length=AppConfig.LOCAL_AUTH.PASSWORD.LENGTH_MAX,
    )

    @pydantic.field_validator("username")
    @classmethod
    def _validate_forbidden_username(cls, v: str | None) -> str | None:
        return v if v is None else validators.username_is_not_forbidden(v)
