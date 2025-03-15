import uuid
from datetime import UTC, datetime

import pydantic

from services.auth.models import JWT
from utils import validators

from .types import SESSION_PROVIDER, SESSION_TYPE


class Session(pydantic.BaseModel):
    """A `Session` of a `User`."""

    id: str
    user_id: uuid.UUID
    is_valid: bool
    created_at: datetime
    expires_at: datetime
    provider: SESSION_PROVIDER
    type: SESSION_TYPE

    @pydantic.computed_field  # type: ignore[prop-decorator]
    @property
    def is_expired(self) -> bool:
        return self.expires_at < datetime.now(UTC).replace(microsecond=0)

    @pydantic.field_validator("created_at", "expires_at")
    @classmethod
    def _validate_datetimes(cls, v: datetime, info: pydantic.ValidationInfo) -> datetime:
        return validators.datetime_has_timezone_utc(cls.__name__, str(info.field_name), v)

    @pydantic.field_serializer("user_id", when_used="always")
    def _serialize_user_id(self, v: uuid.UUID) -> str:
        return str(v)

    @pydantic.field_serializer("created_at", "expires_at", when_used="json")
    def _serialize_dates(self, v: datetime) -> str:
        return str(v)

    @staticmethod
    def from_jwt(jwt: JWT, type: SESSION_TYPE) -> "Session":
        return Session(
            id=jwt.jti,
            user_id=uuid.UUID(jwt.sub),
            created_at=jwt.iat,
            expires_at=jwt.exp,
            is_valid=True,
            provider=jwt.iss,
            type=type,
        )
