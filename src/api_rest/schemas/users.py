from datetime import datetime

import pydantic

from config import AppConfig
from services.users import NormalUser
from utils import validators


class UserShortResponse(pydantic.BaseModel):
    """Response body containing the short details of a normal `User`."""

    email: pydantic.EmailStr
    username: str
    created_at: datetime = pydantic.Field(default=None)  # type: ignore

    @pydantic.field_serializer("created_at", when_used="json")
    def _serialize_dates(self, v: datetime) -> str:
        return str(v.replace(microsecond=0))


class UserFullResponse(NormalUser):
    """Response body containing the full details of a normal `User`."""


class UserRegisterRequest(pydantic.BaseModel):
    """Request body for registering a new `User`."""

    email: pydantic.EmailStr = pydantic.Field(
        min_length=5,
        max_length=255,
    )
    password: str = pydantic.Field(
        min_length=AppConfig.LOCAL_AUTH.PASSWORD.LENGTH_MIN,
        max_length=AppConfig.LOCAL_AUTH.PASSWORD.LENGTH_MAX,
    )


class UserUpdateRequest(pydantic.BaseModel):
    """Request body for updating an existing `User`."""

    email: pydantic.EmailStr | None = pydantic.Field(
        default=None,
        min_length=5,
        max_length=255,
    )
    username: str | None = pydantic.Field(
        default=None,
        min_length=AppConfig.USERS.USERNAME_LENGTH_MIN,
        max_length=AppConfig.USERS.USERNAME_LENGTH_MAX,
    )

    @pydantic.field_validator("username")
    @classmethod
    def _validate_forbidden_username(cls, v: str | None) -> str | None:
        return v if v is None else validators.username_is_not_forbidden(v)


class UserUpdatePasswordRequest(pydantic.BaseModel):
    """Request body for updating the password of an existing `User`."""

    current_password: str | None = None
    new_password: str = pydantic.Field(
        min_length=AppConfig.LOCAL_AUTH.PASSWORD.LENGTH_MIN,
        max_length=AppConfig.LOCAL_AUTH.PASSWORD.LENGTH_MAX,
    )
