import hashlib
import typing
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache

import pydantic

from config import AppConfig
from utils import validators
from utils.extensions import (
    BaseFieldMeta,
    EnchancedModelMixin,
    make_field_extender,
    make_field_with_meta,
)

from .types import USER_LOGIN_PROVIDER


####################
#   Users
####################


@dataclass(eq=False, slots=True)
class FieldConfig(BaseFieldMeta):
    is_visible: bool = False
    """(NB currently not used) If the field's value is visible to the `User`."""
    is_updatable: bool = False
    """If the field's value can be updated by the `User`."""
    is_unique: bool = False
    """If only one `User` can have a specific value for that field."""


Field, FieldsWithMetaMixin = make_field_with_meta(field_factory=pydantic.Field, metadata_type=FieldConfig)
extend = make_field_extender(Field)  # type: ignore


class BaseUser(EnchancedModelMixin, pydantic.BaseModel, FieldsWithMetaMixin):
    """A base model for different types of `Users`."""

    model_config = pydantic.ConfigDict(frozen=True, extra="forbid")

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    email: pydantic.EmailStr | None
    username: str = Field(FieldConfig(is_unique=True, is_visible=True))
    password: str | None
    is_admin: bool
    is_admin_super: bool
    logins_from: list[USER_LOGIN_PROVIDER] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(microsecond=0))
    is_deleted: bool = Field(default=False)
    deleted_at: datetime = Field(default=datetime.min.replace(microsecond=0, tzinfo=UTC))

    @pydantic.field_validator("created_at", "deleted_at")
    @classmethod
    def _validate_dates(cls, v: datetime) -> datetime:
        return validators.datetime_has_timezone_utc(cls.__name__, "created_at", v)

    @pydantic.field_serializer("id", when_used="always")
    def _serialize_id(self, v: uuid.UUID) -> str:
        return str(v)

    @pydantic.field_serializer("password", when_used="json")
    def _serialize_password(self, v: str) -> str | None:
        return None if v is None else "*****"

    @pydantic.field_serializer("created_at", "deleted_at", when_used="json")
    def _serialize_dates(self, v: datetime) -> str:
        return str(v.replace(microsecond=0))

    @classmethod
    @cache
    def fields_unique(cls) -> list[str]:
        """List of field names that are supposed to be unique accross all `Users`."""
        return [f_name for f_name, f_meta in cls.fields_meta().items() if f_meta.is_unique]

    @classmethod
    @cache
    def fields_updatable_by_user(cls) -> set[str]:
        """Set of field names that a `User` can update."""
        return set(f_name for f_name, f_meta in cls.fields_meta().items() if f_meta.is_updatable)

    @classmethod
    @cache
    def fields_visible(cls) -> list[str]:
        """List of field names that a `User` can see."""
        return [f_name for f_name, f_meta in cls.fields_meta().items() if f_meta.is_visible]


class AdminUser(BaseUser):
    """An ADMIN `User`."""

    id: uuid.UUID = extend(
        # BaseUserModel.id,
        BaseUser.model_fields["id"],
        FieldConfig(is_visible=True),
    )
    password: str
    email: typing.Literal[None] = extend(
        # BaseUserModel.email,
        BaseUser.model_fields["email"],
        default=None,  # type: ignore
    )
    is_admin: typing.Literal[True] = extend(
        # BaseUserModel.is_admin,
        BaseUser.model_fields["is_admin"],
        FieldConfig(is_visible=True),
        default=True,  # type: ignore
    )
    is_admin_super: bool = False
    created_at: datetime = extend(
        # BaseUserModel.created_at,
        BaseUser.model_fields["created_at"],
        FieldConfig(is_visible=True),
    )


class NormalUser(BaseUser):
    """A regular `User`."""

    email: pydantic.EmailStr = extend(
        # BaseUserModel.email,
        BaseUser.model_fields["email"],
        FieldConfig(is_unique=True, is_updatable=True, is_visible=True),
        min_length=5,
        max_length=255,
    )
    username: str = extend(
        # BaseUserModel.username,
        BaseUser.model_fields["username"],
        FieldConfig(is_updatable=True),
        default=None,  # type: ignore
    )
    is_admin: typing.Literal[False] = extend(
        # BaseUserModel.is_admin,
        BaseUser.model_fields["is_admin"],
        default=False,  # type: ignore
    )
    is_admin_super: typing.Literal[False] = False

    @typing.override
    def model_post_init(self, _: typing.Any):
        if self.username is None:
            self.model_config["frozen"] = False
            self.username = (
                "User_"
                + str(int.from_bytes(hashlib.md5(self.email.encode()).digest()))[
                    : AppConfig.USERS.USERNAME_LENGTH_INITIAL_SUFFIX
                ]
            )
            self.model_config["frozen"] = True


class UserLogin(pydantic.BaseModel):
    """Tracker of the count of logins of a given `User` using a given auth provider.

    `Sessions` are by definition ephemeral and not suitable for this purpouse.
    """

    user: BaseUser
    provider: USER_LOGIN_PROVIDER
    logins_count: int = Field(default=0)


####################
#   WebHooks
####################


class WebHookClient(pydantic.BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    external_id: str
    is_enabled: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebHook(pydantic.BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    client: WebHookClient
    destination: str  # url
    protocol: typing.Literal["grpc", "http"]


class WebHookGRPC(WebHook):
    protocol: typing.Literal["grpc"] = "grpc"


class WebHookHTTP(WebHook):
    protocol: typing.Literal["http"] = "http"
