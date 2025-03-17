import enum
import typing

import pydantic
from pydantic_settings import SettingsConfigDict

from utils import logging, singleton

from . import _utils


log = logging.getLogger()


_LOCAL_AUTH_ENV_PREFIX: typing.Final[str] = "AUTH_LOCAL"


class _LocalAuthCookieConfig(_utils.BaseSettings):
    """Configs for a local authentication with a Cookie."""

    _prefix: typing.ClassVar[str] = f"{_LOCAL_AUTH_ENV_PREFIX}_COOKIE"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix, serialization_alias="IS_ENABLED")
    NAME: str = None  # type: ignore
    EXPIRE_MINUTES: pydantic.PositiveInt = None  # type: ignore

    def _validate_when_enabled(self) -> typing.Self:
        if self.IS_ENABLED:
            if self.NAME is None:
                raise _utils.missing_required_field_error(self._prefix, "NAME")
            if self.EXPIRE_MINUTES is None:
                raise _utils.missing_required_field_error(self._prefix, "EXPIRE_MINUTES")
        return self


class _LocalAuthTokenConfig(_utils.BaseSettings):
    """Configs for a local authentication with an Access Token."""

    _prefix: typing.ClassVar[str] = f"{_LOCAL_AUTH_ENV_PREFIX}_ACCESS_TOKEN"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix, serialization_alias="IS_ENABLED")
    EXPIRE_MINUTES: pydantic.PositiveInt = None  # type: ignore

    def _validate_when_enabled(self) -> typing.Self:
        if self.IS_ENABLED and self.EXPIRE_MINUTES is None:
            raise _utils.missing_required_field_error(self._prefix, "EXPIRE_MINUTES")
        return self


class LocalAuthConfig(_utils.BaseSettings):
    """Configs for a local authentication."""

    _prefix: typing.ClassVar[str] = _LOCAL_AUTH_ENV_PREFIX
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix, serialization_alias="IS_ENABLED")
    COOKIE: _LocalAuthCookieConfig = pydantic.Field(None, alias="", serialization_alias="COOKIE")  # type: ignore
    ACCESS_TOKEN: _LocalAuthTokenConfig = pydantic.Field(None, alias="", serialization_alias="ACCESS_TOKEN")  # type: ignore
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: pydantic.PositiveInt = pydantic.Field(None)  # type: ignore

    @typing.override
    def model_post_init(self, _: typing.Any):
        self.model_config["frozen"] = False
        self.COOKIE = _utils.with_correct_env_prefix_on_error(_LocalAuthCookieConfig)
        self.ACCESS_TOKEN = _utils.with_correct_env_prefix_on_error(_LocalAuthTokenConfig)
        self.model_config["frozen"] = True
        if self.IS_ENABLED:
            self.COOKIE._validate_when_enabled()
            self.ACCESS_TOKEN._validate_when_enabled()
            msg = "'cookie'" if self.COOKIE.IS_ENABLED else ""
            if self.ACCESS_TOKEN.IS_ENABLED:
                msg = f"{msg}, 'token'" if msg else "'token'"
            log.info(f"enabled: [{msg}]")
        else:
            log.info("disabled")


_EXTERNAL_AUTH_ENV_PREFIX: typing.Final[str] = "AUTH"


class _OAuth2ProviderConfig(_utils.BaseSettings, singleton.SingletonPydantic):
    """Common configs for authentication with an external OAuth2 provider."""

    IS_ENABLED: bool
    CLIENT_ID: str = None  # type: ignore
    CLIENT_SECRET: str = None  # type: ignore
    ACCESS_TOKEN_EXPIRE_MINUTES: pydantic.PositiveInt = None  # type: ignore

    @pydantic.model_validator(mode="after")
    def _ensure_required(self) -> typing.Self:
        if self.IS_ENABLED:
            prefix = self.model_config.get("env_prefix", "")
            if self.CLIENT_ID is None:
                raise _utils.missing_required_field_error(prefix, "CLIENT_ID")
            if self.CLIENT_SECRET is None:
                raise _utils.missing_required_field_error(prefix, "CLIENT_SECRET")
            if self.ACCESS_TOKEN_EXPIRE_MINUTES is None:
                raise _utils.missing_required_field_error(prefix, "ACCESS_TOKEN_EXPIRE_MINUTES")
        return self

    @pydantic.field_serializer("CLIENT_SECRET")
    def _serialize_secrets(self, _: str) -> str:
        return "*****"


class _DiscordOAuth2(_OAuth2ProviderConfig):
    """Configs for authentication with Discord."""

    _prefix: typing.ClassVar[str] = f"{_EXTERNAL_AUTH_ENV_PREFIX}_DISCORD"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix)


class _FacebookOAuth2(_OAuth2ProviderConfig):
    """Configs for authentication with Facebook."""

    _prefix: typing.ClassVar[str] = f"{_EXTERNAL_AUTH_ENV_PREFIX}_FACEBOOK"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix)


class _GitHubOAuth2(_OAuth2ProviderConfig):
    """Configs for authentication with GitHub."""

    _prefix: typing.ClassVar[str] = f"{_EXTERNAL_AUTH_ENV_PREFIX}_GITHUB"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix)


class _GoogleOAuth2(_OAuth2ProviderConfig):
    """Configs for authentication with Google."""

    _prefix: typing.ClassVar[str] = f"{_EXTERNAL_AUTH_ENV_PREFIX}_GOOGLE"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix)


class _LinkedInOAuth2(_OAuth2ProviderConfig):
    """Configs for authentication with LinkedIn."""

    _prefix: typing.ClassVar[str] = f"{_EXTERNAL_AUTH_ENV_PREFIX}_LINKEDIN"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix)


class _MicrosoftOAuth2(_OAuth2ProviderConfig):
    """Configs for authentication with Microsoft."""

    _prefix: typing.ClassVar[str] = f"{_EXTERNAL_AUTH_ENV_PREFIX}_MICROSOFT"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix)


class _RedditOAuth2(_OAuth2ProviderConfig):
    """Configs for authentication with Reddit."""

    _prefix: typing.ClassVar[str] = f"{_EXTERNAL_AUTH_ENV_PREFIX}_REDDIT"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=_prefix)


@enum.unique
class OAuth2Provider(enum.StrEnum):
    """An external OAuth2 provider."""

    DISCORD = ("discord", _DiscordOAuth2)
    FACEBOOK = ("facebook", _FacebookOAuth2)
    GITHUB = ("github", _GitHubOAuth2)
    GOOGLE = ("google", _GoogleOAuth2)
    LINKEDIN = ("linkedin", _LinkedInOAuth2)
    MICROSOFT = ("microsoft", _MicrosoftOAuth2)
    REDDIT = ("redit", _RedditOAuth2)

    def __new__(cls, name: str, config_class: type[_OAuth2ProviderConfig]):
        member = str.__new__(cls, name)
        member._value_ = name
        return member

    def __init__(self, name: str, config_class: type[_OAuth2ProviderConfig]):
        self.config_class = config_class


class OAuth2Config(pydantic.BaseModel, frozen=True):
    """All configs specific for external OAuth2 authentication."""

    model_config = pydantic.ConfigDict(
        extra="forbid",
        validate_default=True,
        validate_assignment=True,
        hide_input_in_errors=True,
    )

    REDIRECT_ROUTE_PATH: typing.Literal["/oauth2-redirect"] = "/oauth2-redirect"
    REDIRECT_ROUTE_NAME: typing.Literal["auth:oauth2-redirect"] = "auth:oauth2-redirect"
    SWAGGERUI_TOKEN_PATH: typing.Literal["/internal/oauth2-swaggerui-token"] = "/internal/oauth2-swaggerui-token"
    ENABLED_PROVIDERS: list[OAuth2Provider] = []
    __configs_for_enabled: typing.ClassVar[dict[OAuth2Provider, _OAuth2ProviderConfig]] = {}

    @typing.override
    def model_post_init(self, _: typing.Any):
        self.__configs_for_enabled.update(
            {
                provider: config_instance
                for provider, config_instance in [
                    (value, value.config_class()) for value in OAuth2Provider.__members__.values()
                ]
                if config_instance.IS_ENABLED
            }
        )
        self.ENABLED_PROVIDERS.extend(p for p in self.__configs_for_enabled.keys())
        log.info(f"enabled: {[p.value for p in self.ENABLED_PROVIDERS]}")
        self.model_config["frozen"] = True  # runtime error, no static-type-check error

    def config_for(self, provider: str | OAuth2Provider) -> _OAuth2ProviderConfig:
        """Get the supplied configs for the OAuth2 `provider`.

        :raise ValueError:
            If `provider` wasn't configured
        :raise TypeError:
            If `provider` is not an `OAuth2Provider`.
        """
        if isinstance(provider, str):
            provider = OAuth2Provider._value2member_map_.get(provider, provider)  # type: ignore
        if not isinstance(provider, OAuth2Provider):
            raise TypeError(f"'{provider}' is not an <OAuth2Provider>")
        try:
            return self.__configs_for_enabled[provider]
        except KeyError:
            raise ValueError(f"provider '{provider.name}' is not configured")

    @pydantic.model_serializer(mode="wrap")
    def _serialize_model(self, serializer: pydantic.SerializerFunctionWrapHandler) -> dict[str, typing.Any]:
        res = serializer(self)
        res["PROVIDERS_CONFIG"] = {k: v.model_dump() for k, v in self.__configs_for_enabled.items()}
        return res
