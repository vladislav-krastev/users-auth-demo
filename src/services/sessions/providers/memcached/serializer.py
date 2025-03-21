import typing

from pymemcache.serde import (
    get_python_memcache_serializer,
    python_memcache_deserializer,
)

from config.auth import OAuth2Provider
from services.sessions.types import SESSION_TYPE

from .models import SessionModel


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
        if isinstance(value, SessionModel):
            return cls._serialize_session(value)
        return get_python_memcache_serializer()(key, value)

    @classmethod
    def _serialize_session(cls, session: SessionModel) -> tuple[str, int]:
        flag = FLAG + FLAGS_TYPE.index(session.type) + FLAGS_PROVIDER.index(session.provider)
        return f"{session.u_id} {session.expires_at}", flag

    @classmethod
    def deserialize(cls, key: str, value: bytes, flags: int):
        if (flags & FLAG) == FLAG:
            return cls._deserialize_session(key, value, flags)
        return python_memcache_deserializer(key, value, flags)

    @classmethod
    def _deserialize_session(cls, key: str, value: bytes, flags: int) -> SessionModel:
        decoded = value.decode("ascii").split()
        flags ^= FLAG
        type_index = flags % 2
        provider_index = flags - type_index
        return SessionModel(
            key,
            decoded[0],
            int(decoded[1]),
            FLAGS_PROVIDER[provider_index],
            FLAGS_TYPE[type_index],
        )
