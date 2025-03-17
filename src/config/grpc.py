import typing

import pydantic
from pydantic_settings import SettingsConfigDict

from . import _utils


class GrpcConfig(_utils.BaseSettings):
    """Configs for the gRPC server."""

    _prefix: typing.ClassVar[str] = "GRPC"
    model_config = SettingsConfigDict(env_prefix=f"{_prefix}_")
    IS_ENABLED: bool = pydantic.Field(False, alias=f"{_prefix}_ENABLED", serialization_alias="IS_ENABLED")
    PORT: pydantic.PositiveInt
