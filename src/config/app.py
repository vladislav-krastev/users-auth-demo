import typing

import pydantic

from utils import logging, singleton

from . import _utils, auth, grpc, sessions, users


log = logging.getLogger()


# being a Singleton is just a precaution, everything should be using the 'AppConfig' instance:
class _AppConfig(_utils.BaseSettings, singleton.SingletonPydantic):
    """ """

    APP_NAME: str
    HOST_URL: str
    SECRET_KEY: str

    LOCAL_AUTH: auth.LocalAuthConfig = pydantic.Field(
        default_factory=lambda: _utils.init_config(auth.LocalAuthConfig, "[AUTH LOCAL]")
    )
    OAUTH2: auth.OAuth2Config = pydantic.Field(
        default_factory=lambda: _utils.init_config(auth.OAuth2Config, "[AUTH EXTERNAL]")
    )
    SESSIONS: sessions.SessionsConfig = pydantic.Field(
        default_factory=lambda: _utils.init_config(sessions.SessionsConfig, "[SESSIONS]")
    )
    USERS: users.UsersConfig = pydantic.Field(default_factory=lambda: _utils.init_config(users.UsersConfig, "[USERS]"))
    GRPC: grpc.GrpcConfig = pydantic.Field(default_factory=lambda: _utils.init_config(grpc.GrpcConfig, "[GRPC]"))

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

    @pydantic.field_serializer("SECRET_KEY")
    def _serialize_secrets(self, _: str) -> str:
        return "*****"


with log.any_error(exit_code=1):
    with log.with_prefix("[CONFIG]"):
        log.info("starting ...")
        AppConfig: typing.Final[_AppConfig] = _AppConfig()
        log.info("success!")
