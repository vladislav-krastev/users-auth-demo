import typing

import pydantic
from pydantic_settings import SettingsConfigDict

from utils import logging, singleton

from . import _utils, auth, grpc, sessions, users


log = logging.getLogger()


# being a Singleton is just a precaution, everything should be using the 'AppConfig' instance:
class _AppConfig(_utils.BaseSettings, singleton.SingletonPydantic):
    """ """

    model_config = SettingsConfigDict(frozen=False)

    APP_NAME: str
    HOST_URL: str
    SECRET_KEY: str

    LOCAL_AUTH: auth.LocalAuthConfig = pydantic.Field(default=None)  # type: ignore
    OAUTH2: auth.OAuth2Config = pydantic.Field(default=None)  # type: ignore
    SESSIONS: sessions.SessionsConfig = pydantic.Field(default=None)  # type: ignore
    USERS: users.UsersConfig = pydantic.Field(default=None)  # type: ignore
    GRPC: grpc.GrpcConfig = pydantic.Field(default=None)  # type: ignore

    @property
    def are_both_storage_providers_on_same_rdbms(self) -> bool:
        """ """
        if not (
            AppConfig.SESSIONS.PROVIDER == sessions.SessionsProvider.RDBMS
            and AppConfig.SESSIONS.PROVIDER == AppConfig.USERS.PROVIDER
        ):
            return False
        AppConfig.SESSIONS.PROVIDER_CONFIG = typing.cast(
            sessions.RDBMSProviderConfig, AppConfig.SESSIONS.PROVIDER_CONFIG
        )
        AppConfig.USERS.PROVIDER_CONFIG = typing.cast(users.RDBMSProviderConfig, AppConfig.USERS.PROVIDER_CONFIG)
        return AppConfig.SESSIONS.PROVIDER_CONFIG.CONNECTION_URL == AppConfig.USERS.PROVIDER_CONFIG.CONNECTION_URL

    @typing.override
    def model_post_init(self, _: typing.Any):
        with log.with_prefix("[AUTH LOCAL]"):
            self.LOCAL_AUTH = _utils.with_correct_env_prefix_on_error(auth.LocalAuthConfig)
        with log.with_prefix("[AUTH EXTERNAL]"):
            self.OAUTH2 = auth.OAuth2Config()
        with log.with_prefix("[SESSIONS]"):
            self.SESSIONS = _utils.with_correct_env_prefix_on_error(sessions.SessionsConfig)
        with log.with_prefix("[USERS]"):
            self.USERS = _utils.with_correct_env_prefix_on_error(users.UsersConfig)
        with log.with_prefix("[GRPC]"):
            self.GRPC = _utils.with_correct_env_prefix_on_error(grpc.GrpcConfig)
        self.model_config["frozen"] = True  # runtime error, no static-type-check error

    @pydantic.field_serializer("SECRET_KEY")
    def _serialize_secrets(self, _: str) -> str:
        return "*****"


with log.any_error(exit_code=1):
    with log.with_prefix("[CONFIG]"):
        log.info("starting ...")
        AppConfig: typing.Final[_AppConfig] = _AppConfig()
        log.info("success!")
