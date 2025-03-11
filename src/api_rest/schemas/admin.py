import typing
import uuid
from datetime import datetime

import pydantic

from services.sessions import Session
from services.users import NormalUser
from utils import validators


class AdminCreateRequest(pydantic.BaseModel):
    """Request body for registering a new ADMIN `User`."""

    username: str = pydantic.Field(
        min_length=5,
        max_length=20,
    )
    password: str = pydantic.Field(
        min_length=3,
        max_length=20,
    )

    @pydantic.field_validator("username")
    @classmethod
    def _validate_forbidden_username(cls, v: str | None) -> str | None:
        return v if v is None else validators.username_is_not_forbidden(v)


class AdminResponse(pydantic.BaseModel):
    """Response body for getting the details of an ADMIN `User`."""

    is_admin: typing.Literal[True]
    id: uuid.UUID
    username: str
    created_at: datetime
    # logins_from: list[typing.Any]

    @pydantic.field_serializer("id", "created_at", when_used="json")
    def _to_string(self, v: uuid.UUID | datetime) -> str:
        return str(v)


class AdminGetUserResponse(NormalUser):
    """Response body for getting the details of a normal `User` as an ADMIN `User`."""


class AdminGetSessionResponse(Session):
    """Response body for getting the details of a `Session` as an ADMIN `User`."""


class AdminGetAllActiveSessionsResponse(pydantic.BaseModel):
    """ """
