import enum
import typing

import pydantic
from pydantic_core import MultiHostUrl
from pydantic_settings import SettingsConfigDict

from utils import logging, password, singleton

from . import _utils


class SessionsProviderConfig(_utils.BaseSettings, singleton.SingletonPydantic):
    """Configs for a `Sessions` storage provider."""

    _prefix: typing.ClassVar[str] = "SESSIONS_PROVIDER"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")


class DynamoDBProvider(SessionsProviderConfig):
    """Configs for storing the `Sessions` in `DynamoDB`."""

    AWS_ACCESS_KEY: str
    AWS_SECRET_KEY: str

    @pydantic.field_serializer("AWS_SECRET_KEY")
    def _serialize_secret_key(self, _: str) -> str:
        return "*****"


class MemcachedProvider(SessionsProviderConfig):
    """Configs for storing the `Sessions` in `Memcached`."""

    MEMCACHED_SERVER: str
    MEMCACHED_PORT: pydantic.PositiveInt
    MEMCACHED_RETRIES_BEFORE_FAIL: pydantic.PositiveInt = 5


class RDBMSProvider(SessionsProviderConfig):
    """Configs for storing the `Sessions` in `RDBMS` (currently only PostgreSQL)."""

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

    @pydantic.field_serializer("DB_PASSWORD", when_used="always")
    def _serialize_password(self, _: str) -> str:
        print("in _serialize_password")
        return "*****"

    @pydantic.field_serializer("DB_CONNECT_URL", when_used="always")
    def _serialize_url(self, url: MultiHostUrl) -> str:
        return password.get_obscured_password_db_url(url).unicode_string()


class RedisProvider(SessionsProviderConfig):
    """Configs for storing the `Sessions` in `Redis`."""


class SessionsProvider(enum.StrEnum):
    """A `Sessions` storage provder."""

    DYNAMODB = ("dynamodb", DynamoDBProvider)
    MEMCACHED = ("memcached", MemcachedProvider)
    RDBMS = ("rdbms", RDBMSProvider)
    REDIS = ("redis", RedisProvider)

    def __new__(cls, name: str, config_class: type[SessionsProviderConfig]):
        member = str.__new__(cls, name)
        member._value_ = name
        return member

    def __init__(self, name: str, config_class: type[SessionsProviderConfig]):
        self.config_class = config_class


class SessionsConfig(_utils.BaseSettings):
    """ """

    _prefix: typing.ClassVar[str] = "SESSIONS"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_", frozen=False)

    PROVIDER: SessionsProvider
    PROVIDER_CONFIG: SessionsProviderConfig = pydantic.Field(default=None)  # type: ignore

    EXPIRED_DELETE: bool = False
    EXPIRED_DELETE_AFTER_MINS: pydantic.PositiveInt = pydantic.Field(default=None)  # type: ignore

    @pydantic.model_validator(mode="after")
    def _validate_expired_delete(self) -> typing.Self:
        if self.EXPIRED_DELETE and (self.EXPIRED_DELETE_AFTER_MINS is None):
            raise _utils.missing_required_field_error(self._prefix, "EXPIRED_DELETE_AFTER_MINS")
        return self

    @typing.override
    def model_post_init(self, _: typing.Any):
        self.PROVIDER_CONFIG = _utils.with_correct_env_prefix_on_error(
            SessionsProvider(self.PROVIDER).config_class,
        )
        logging.getLogger().info(f"[PROVIDER] {self.PROVIDER}")
        self.model_config["frozen"] = True  # runtime error, no static-type-check error

    @pydantic.field_serializer("PROVIDER_CONFIG")
    def _serialize_config(self, provider_config: SessionsProviderConfig) -> dict[str, typing.Any]:
        return provider_config.model_dump()
