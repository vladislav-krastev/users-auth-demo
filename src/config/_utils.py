"""Utilities related only to and used only by the configurations."""

import pathlib

import pydantic
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings as PydanticBaseSettings
from pydantic_settings import SettingsConfigDict

from utils import logging


log = logging.getLogger()


class BaseSettings(PydanticBaseSettings):
    """Provides a common base `model_config` attribute for the config classes."""

    model_config = SettingsConfigDict(
        env_file=pathlib.Path(__file__).parent.joinpath("../../.env").resolve(),  # TODO: ugly path ...
        frozen=True,  # runtime error, no static-type-check error
        extra="ignore",
        case_sensitive=True,
        env_ignore_empty=True,
        validate_default=False,
        validate_assignment=True,
        hide_input_in_errors=True,
    )


def init_config[T: BaseSettings | PydanticBaseSettings | pydantic.BaseModel](
    model: type[T], log_prefix: str | None = None
) -> T:
    """Initialise a configuration namespace.

    If a `pydantic.ValidationError` is thrown during the instance creation,
    its reraised with included the 'correct' (from the user's perspective)
    name of the errored field, prefixed with the specific `model.model_config["env_prefix"]`.

    :param type[T] model:
        The class to be initialised.
    :param str log_prefix:
        Optional text to prefix any logs emitted during initialisation.

    :return T:
        An instance of the `model`.
    """
    try:
        with log.with_prefix(log_prefix):
            return model()
    except pydantic.ValidationError as err:
        e = err.errors()[0]
        if e["loc"]:  # info for an errored field is present
            raise PydanticCustomError(  # show errored field name with correct 'env_prefix'
                f"{e['type']}",  # type: ignore
                "{p}{f}: {m}",
                {"p": model.model_config.get("env_prefix", ""), "f": e["loc"][0], "m": e["msg"]},
            )
        raise err


def missing_required_field_error(prefix: str, name: str) -> PydanticCustomError:
    """An error for required but missing configuration field."""

    return PydanticCustomError(
        "missing", "{p}_{n}: Field required", {"p": prefix[:-1] if prefix.endswith("_") else prefix, "n": name}
    )
