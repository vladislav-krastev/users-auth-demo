import pydantic
from pydantic_settings import SettingsConfigDict

from . import _utils


class GrpcConfig(_utils.BaseSettings):
    """Configs for the gRPC server."""

    model_config = SettingsConfigDict(env_prefix="GRPC_")
    # SERVER: str = ""
    PORT: pydantic.PositiveInt
