import typing
from datetime import UTC, datetime

from pymemcache.client.base import Client as _MemcacheClient
from pymemcache.serde import (
    python_memcache_deserializer,
    python_memcache_serializer,
)

from config.sessions import MemcachedProvider
from utils import logging

from ..abstract import BaseSessionsProvider, Session
from .models import NOW, UserSessionsModel


log = logging.getLogger("sessions-memcached")


class SessionsProviderMemcached(BaseSessionsProvider):
    """ """

    __slots__ = ("_connection_url", "_client")

    def __init__(self, config: MemcachedProvider) -> None:
        self._connection_url = f"{config.MEMCACHED_SERVER}:{config.MEMCACHED_PORT}"
        self._client = _MemcacheClient(
            self._connection_url,
            serializer=python_memcache_serializer,
            deserializer=python_memcache_deserializer,
            default_noreply=False,
        )

    @typing.override
    async def validate_connection(self) -> bool:
        try:
            res = self._client.set("test_key", "test_value")
            if not (res and self._client.delete("test_key")):
                raise ValueError("Unknown connection error")
        except Exception as err:
            log.error(f"Could not establish connection to: {self._connection_url}: {err}")
            return False
        log.info(f"established connection to: {self._connection_url}")
        return True

    @typing.override
    async def create(self, s: Session) -> Session | None:
        user_sessions = UserSessionsModel(user_id=str(s.user_id), sessions=self._client.get(str(s.user_id), None))
        update_method = self._client.add if user_sessions.sessions is None else self._client.replace
        user_sessions.update(s)
        update_method(
            key=user_sessions.user_id,
            value=user_sessions.sessions,
        )
        expires_at = s.expires_at.timestamp()
        self._client.add(
            key=s.id,
            value=(s.id, str(s.user_id), str(expires_at)),
            expire=int(expires_at - NOW() + 1),
        )
        return s

    @typing.override
    async def get(self, u_id: str, s_id: str) -> Session | None:
        res = self._client.get(s_id)
        print(res)
        expires_at_timestamp = float(res[2])
        expires_at = datetime.fromtimestamp(expires_at_timestamp, UTC)
        # AppConfig.LOCAL_AUTH.
        # r = expires_at_timestamp - timedelta()
        # s = Session(
        #     id=res[0],
        #     user_id=uuid.UUID(res[1]),
        #     is_valid=True,
        #     created_at=datetime(),
        #     expires_at=expires_at,
        # )
        raise NotImplementedError()

    @typing.override
    async def get_many(
        self, u_id: str, *u_ids: str, offset: int, limit: int | None, include_expired: bool
    ) -> list[Session]:
        raise NotImplementedError()

    @typing.override
    async def invalidate(self, u_id: str, s_id: str) -> bool:
        raise NotImplementedError()

    @typing.override
    async def invalidate_all(self, u_id: str) -> bool:
        raise NotImplementedError()

    @typing.override
    async def delete_old(self, u_id: str, *u_ids: str, only_expired: bool = False, only_invalid: bool = False) -> bool:
        raise NotImplementedError()
