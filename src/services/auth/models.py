import hashlib
import typing
from datetime import datetime, timedelta, timezone

import jwt
import pydantic
from pydantic_core.core_schema import ValidationInfo as pydantic_ValidationInfo

from config import AppConfig
from services.sessions.types import SESSION_PROVIDER
from services.users.models import BaseUser
from utils import exceptions, validators


_ALGORITHM = "HS256"


class JWT(pydantic.BaseModel):
    """A JWT model with utility methods.

    Used as a cookie-value in cookie-based auths and as an access-token in OAuth2-based auths.
    """

    model_config = pydantic.ConfigDict(extra="forbid")

    iss: str = ""
    aud: str = ""
    iat: datetime
    nbf: datetime = None  # type: ignore
    exp: datetime
    jti: str = ""
    sub: str

    @pydantic.field_validator("iat", "nbf", "exp")
    @classmethod
    def _validate_timestamps(cls, v: datetime, info: pydantic_ValidationInfo) -> datetime:
        return validators.datetime_has_timezone_utc(cls.__name__, str(info.field_name), v)

    @classmethod
    def create_for_user(cls, user: BaseUser, expire_mins: int, provider: SESSION_PROVIDER) -> "JWT":
        """Create a new `JWT` based on the provided `User` and aditional configs."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=expire_mins)
        hash_from = user.username if user.email is None else str(user.email)
        token_id = hashlib.md5((hash_from + str(now.timestamp())).encode()).hexdigest()
        return JWT(
            # iss="users-auth",  # TODO: config for APP_NAME, where else to use it?
            # aud=str(provider),  # NOTE: for external auth, the 'iss' and 'aud' are technically reversed
            iat=now,
            exp=expires_at,
            jti=token_id,
            sub=str(user.id),
        )

    def encode(self) -> str:
        """Encode the `JWT` to a string."""
        return jwt.encode(
            self.model_dump(
                exclude_none=True,
                exclude_unset=True,
                exclude_defaults=True,
            ),
            key=AppConfig.SECRET_KEY,
            algorithm=_ALGORITHM,
        )

    @classmethod
    def decode(cls, token: str) -> "JWT":
        """Try decoding the `token` string to a valid new `JWT`."""
        try:
            return JWT(
                **jwt.decode(
                    token,
                    key=AppConfig.SECRET_KEY,
                    algorithms=[_ALGORITHM],
                    # issuer="users-auth",
                )
            )
        except (jwt.exceptions.InvalidTokenError, pydantic.ValidationError) as err:
            raise exceptions.InvalidJWTError(err.args)

    def validate_provider(self) -> bool:
        """Validate the auth provider of the `JWT` is still enabled."""
        return self.aud == "local" or self.aud in AppConfig.OAUTH2.ENABLED_PROVIDERS


class Cookie(pydantic.BaseModel):
    """A browser Cookie."""

    model_config = pydantic.ConfigDict(extra="forbid")

    key: str
    value: str
    max_age: int | None = None
    expires: datetime | str | int | None = None
    domain: str | None = None  # TODO: if not set, cookie is not sent for subdomain requests!!!
    path: str | None = "/"  # TODO: probably needs to be more specific (depends on how will the app be deployed)
    secure: typing.Literal[True] = True
    httponly: typing.Literal[True] = True
    samesite: typing.Literal["lax", "strict", "none"] = (
        "lax"  # TODO: think about this (depends on how will the app be deployed ?)
    )


class AccessToken(pydantic.BaseModel):
    """An Access Token of type `Bearer`."""

    model_config = pydantic.ConfigDict(extra="forbid")

    token_type: typing.Literal["Bearer"] = "Bearer"
    access_token: str = pydantic.Field(min_length=64)
    expires_in: int | None = None
    scope: str | None = None
    refresh_token: str | None = pydantic.Field(default=None, min_length=64)
