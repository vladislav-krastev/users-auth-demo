import typing
import uuid
from datetime import UTC, datetime, timedelta

from pymemcache.serde import (
    get_python_memcache_serializer,
    python_memcache_deserializer,
)

from config import AppConfig
from config.auth import OAuth2Provider
from services.sessions.models import Session
from services.sessions.types import SESSION_TYPE


FLAG = 1 << 15  # big enough to future-proof against more flags defined in 'pymemcache.serde'
FLAGS_TYPE: tuple[SESSION_TYPE, SESSION_TYPE] = typing.get_args(SESSION_TYPE)
FLAGS_PROVIDER = (
    "local",
    OAuth2Provider.DISCORD,
    OAuth2Provider.FACEBOOK,
    OAuth2Provider.GITHUB,
)


class CustomSerializer:
    """See notes in the class docs for `pymemcache.client.base.Client` for the *.serde* attribute."""

    FLAG_SESSION = 1 << 15

    @classmethod
    def serialize(cls, key, value):
        if isinstance(value, Session):
            return cls._serialize_session(value)
        return get_python_memcache_serializer()(key, value)

    @classmethod
    def _serialize_session(cls, session: Session) -> tuple[str, int]:
        flag = FLAG + FLAGS_TYPE.index(session.type) + FLAGS_PROVIDER.index(session.provider)
        return f"{session.user_id} {int(session.expires_at.timestamp())}", flag

    @classmethod
    def deserialize(cls, key: str, value: bytes, flags: int):
        if (flags & FLAG) == FLAG:
            return cls._deserialize_session(key, value, flags)
        return python_memcache_deserializer(key, value, flags)

    @classmethod
    def _deserialize_session(cls, key: str, value: bytes, flags: int) -> Session:
        """Create a (mem-)cached representation of an internal `Session`."""
        data = value.decode("ascii").split()  # [ user_id (UUID as str), expires_at (int timestamp as str) ]
        flags ^= FLAG
        type_index = flags % 2
        type_ = FLAGS_TYPE[type_index]
        provider_index = flags - type_index
        provider = FLAGS_PROVIDER[provider_index]
        expires_at = datetime.fromtimestamp(int(data[1]), UTC).replace(microsecond=0)
        if provider == "local":
            expires_delta = (
                AppConfig.LOCAL_AUTH.COOKIE.EXPIRE_MINUTES
                if type_ == "cookie"
                else AppConfig.LOCAL_AUTH.ACCESS_TOKEN.EXPIRE_MINUTES
            )
        else:
            expires_delta = AppConfig.OAUTH2.config_for(provider).ACCESS_TOKEN_EXPIRE_MINUTES
        return Session(
            id=key,
            user_id=uuid.UUID(data[0]),
            is_valid=True,
            created_at=expires_at - timedelta(minutes=expires_delta),
            expires_at=expires_at,
            provider=provider,
            type=type_,
        )
