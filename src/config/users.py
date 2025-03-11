import enum
import typing

import pydantic
from pydantic_core import MultiHostUrl, PydanticCustomError
from pydantic_settings import SettingsConfigDict

from utils import logging, password, singleton

from . import _utils


class _UsersProviderConfig(_utils.BaseSettings, singleton.SingletonPydantic):
    """Configs for a `Users` storage provider."""

    _prefix: typing.ClassVar[str] = "USERS_PROVIDER"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")


class DynamoDBProvider(_UsersProviderConfig):
    """Configs for storing the `Users` in `DynamoDB`."""

    AWS_ACCESS_KEY: str
    AWS_SECRET_KEY: str
    # AWS_REGION: str
    # AWS_TABLE_NAME: str

    @pydantic.field_serializer("AWS_SECRET_KEY")
    def _serialize_secret_key(self, _: str) -> str:
        return "*****"


class RDBMSProvider(_UsersProviderConfig):
    """Configs for storing the `Users` in an `RDBMS` (currently only PostgreSQL)."""

    ECHO_SQL: bool = False  # TODO: dynamic/configurable
    DB_CONNECTION_SCHEME: typing.Literal["postgresql+asyncpg"] = "postgresql+asyncpg"
    DB_SERVER: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def DB_CONNECT_URL(self) -> MultiHostUrl:
        return MultiHostUrl.build(
            scheme=self.DB_CONNECTION_SCHEME,
            host=self.DB_SERVER,
            port=self.DB_PORT,
            path=self.DB_NAME,
            username=self.DB_USER,
            password=self.DB_PASSWORD,
        )

    @pydantic.field_serializer("DB_PASSWORD")
    def _serialize_password(self, _: str) -> str:
        return "*****"

    @pydantic.field_serializer("DB_CONNECT_URL")
    def _serialize_url(self, url: MultiHostUrl) -> str:
        return password.get_obscured_password_db_url(url).unicode_string()


class UsersProvider(enum.StrEnum):
    """A `Users` storage provder."""

    DYNAMODB = ("dynamodb", DynamoDBProvider)
    RDBMS = ("rdbms", RDBMSProvider)

    def __new__(cls, name: str, config_class: type[_UsersProviderConfig]):
        member = str.__new__(cls, name)
        member._value_ = name
        return member

    def __init__(self, name: str, config_class: type[_UsersProviderConfig]):
        self.config_class = config_class


class UsersConfig(_utils.BaseSettings):
    """All configs specific for the `Users`."""

    _prefix: typing.ClassVar[str] = "USERS"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_", frozen=False)

    PROVIDER: UsersProvider
    PROVIDER_CONFIG: _UsersProviderConfig = pydantic.Field(default=None)  # type: ignore

    SUPER_ADMIN_USERNAME: typing.Literal["admin"] = "admin"
    SUPER_ADMIN_INITIAL_PASSWORD: typing.Literal["admin"] = "admin"

    USERNAME_FORBIDDEN: set[str] = set()
    USERNAME_LENGTH_INITIAL_SUFFIX: pydantic.PositiveInt = pydantic.Field(ge=5)  # TODO
    USERNAME_LENGTH_MIN: pydantic.PositiveInt = pydantic.Field(ge=1)
    USERNAME_LENGTH_MAX: pydantic.PositiveInt = pydantic.Field(ge=1)

    @pydantic.model_validator(mode="after")
    def _validate_username_lengths(self) -> typing.Self:
        if self.USERNAME_LENGTH_MIN > self.USERNAME_LENGTH_MAX:
            raise PydanticCustomError(
                "less_than_equal",
                "USERS_USERNAME_LENGTH_MIN must be <= USERS_USERNAME_LENGTH_MAX, received {len_min} <= {len_max}",
                {"len_min": self.USERNAME_LENGTH_MIN, "len_max": self.USERNAME_LENGTH_MAX},
            )
        return self

    PASSWORD_LENGTH_MIN: pydantic.PositiveInt = pydantic.Field(ge=1)
    PASSWORD_LENGTH_MAX: pydantic.PositiveInt = pydantic.Field(ge=1)

    @pydantic.model_validator(mode="after")
    def _validate_password_lengths(self) -> typing.Self:
        if self.PASSWORD_LENGTH_MIN > self.PASSWORD_LENGTH_MAX:
            raise PydanticCustomError(
                "less_than_equal",
                "USERS_PASSWORD_LENGTH_MIN must be <= USERS_PASSWORD_LENGTH_MAX, received {len_min} <= {len_max}",
                {"len_min": self.PASSWORD_LENGTH_MIN, "len_max": self.PASSWORD_LENGTH_MAX},
            )
        return self

    @typing.override
    def model_post_init(self, _: typing.Any):
        self.USERNAME_FORBIDDEN.add(self.SUPER_ADMIN_USERNAME)
        self.USERNAME_FORBIDDEN.add("me")
        self.PROVIDER_CONFIG = _utils.with_correct_env_prefix_on_error(
            UsersProvider(self.PROVIDER).config_class,
        )
        logging.getLogger().info(f"[PROVIDER] {self.PROVIDER}")
        self.model_config["frozen"] = True  # runtime error, no static-type-check error

    @pydantic.field_serializer("PROVIDER_CONFIG")
    def _serialize_config(self, provider_config: _UsersProviderConfig) -> dict[str, typing.Any]:
        return provider_config.model_dump()

    @pydantic.field_serializer("SUPER_ADMIN_INITIAL_PASSWORD")
    def _serialize_initial_admin_password(self, _: str) -> str:
        return "*****"
