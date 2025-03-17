import itertools
import typing

from pymemcache.client.base import Client as _MemcacheClient
from pymemcache.client.base import Key as _MemcacheKey
from pymemcache.serde import (
    python_memcache_deserializer,
    python_memcache_serializer,
)

from config import AppConfig
from config.sessions import MemcachedProvider
from utils import logging

from ..abstract import BaseSessionsProvider, Session
from .models import SessionModel, UserSessionModel
from .types import CACHED_SESSION


log = logging.getLogger("sessions-memcached")


class SessionsProviderMemcached(BaseSessionsProvider):
    """ """

    __slots__ = ("_connection_url", "_client")

    def __init__(self, config: MemcachedProvider) -> None:
        self._connection_url = f"{config.MEMCACHED_SERVER}:{config.MEMCACHED_PORT}"
        self._client = _MemcacheClient(
            self._connection_url,
            connect_timeout=5,
            timeout=5,
            no_delay=True,
            default_noreply=False,
            serializer=python_memcache_serializer,
            deserializer=python_memcache_deserializer,
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
        new_session = SessionModel.from_internal(s)
        new_user_session = UserSessionModel(s.id, str(new_session.expires_at))
        cache, cas = typing.cast(tuple[set[UserSessionModel] | None, typing.Any], self._client.gets(new_session.u_id))
        is_user_session_created = True
        if not (cache is None and self._client.add(new_session.u_id, {new_user_session})):
            is_user_session_created = False
            cache = set[UserSessionModel]() if cache is None else UserSessionModel.remove_expired(cache)
            for _ in range(
                typing.cast(MemcachedProvider, AppConfig.SESSIONS.PROVIDER_CONFIG).MEMCACHED_RETRIES_BEFORE_FAIL
            ):
                cache.add(new_user_session)
                if self._client.cas(new_session.u_id, cache, cas):
                    is_user_session_created = True
                    break
                cache, cas = typing.cast(tuple[set[UserSessionModel], typing.Any], self._client.gets(new_session.u_id))
        if is_user_session_created and self._client.add(
            new_session.s_id,
            new_session.to_cache(),
            expire=new_session.expires_at - int(s.created_at.timestamp()) + 1,
        ):
            return s

    @typing.override
    async def get(self, u_id: str, s_id: str) -> Session | None:
        cache: CACHED_SESSION | None = self._client.get(s_id)
        if cache is not None:
            with log.any_error():
                s = SessionModel.from_cache(cache)
                if s.u_id == u_id:
                    return s.to_internal()

    @typing.override
    async def get_many(
        self, u_id: str, *u_ids: str, offset: int, limit: int | None, include_expired: bool
    ) -> list[Session]:
        # NOTE: the cached `Sessions` are set to expire on their .expires_at attribute,
        #       so for this SESSIONS_PROVIDER the `only_expired` and `only_invalid` params are irrelevant.

        # sort ASC on User.id (.get_many() orders the result as the order of its input args):
        cache: dict[_MemcacheKey, set[UserSessionModel] | None] = self._client.get_many(sorted([u_id, *u_ids]))
        if not cache:
            return []
        valid_sessions = typing.cast(
            list[set[UserSessionModel]],
            list(filter(lambda v: v is not None and len(UserSessionModel.remove_expired(v)) > 0, cache.values())),
        )
        session_ids = list(
            itertools.chain(
                *[
                    # sort ASC on Session.expires_at (.get_many() orders the result as the order of its input args):
                    # NOTE: the other SESSION_PROVIDERs (e.g. rdbms) sort on Session.created_at, so this sort
                    #       produces different results if the 'EXPIRE_IN_MINUTES' deltas in AppConfig are different
                    #       for the different providers (and/or for the Cookie vs Token for local auth).
                    [s.id for s in sorted(v, key=lambda s: s.exp)]
                    for v in valid_sessions
                ]
            )
        )
        return [
            SessionModel.from_cache(cached_session).to_internal()
            for cached_session in typing.cast(
                dict[_MemcacheKey, CACHED_SESSION],
                self._client.get_many(session_ids[offset : len(session_ids) if limit is None else offset + limit]),
            ).values()
        ]

    @typing.override
    async def invalidate(self, u_id: str, s_id: str) -> bool:
        cache, cas = typing.cast(tuple[set[UserSessionModel] | None, typing.Any], self._client.gets(u_id))
        if not cache:
            return True
        cache = UserSessionModel.remove_expired(cache)
        invalidated = tuple(filter(lambda s: s.id == s_id, cache))
        if len(invalidated) == 0:
            return True
        if len(invalidated) > 1:
            # TODO: log error
            return False
        for _ in range(
            typing.cast(MemcachedProvider, AppConfig.SESSIONS.PROVIDER_CONFIG).MEMCACHED_RETRIES_BEFORE_FAIL
        ):
            if self._client.cas(u_id, cache.difference(invalidated), cas):
                self._client.delete(s_id)
                return True
            cache, cas = typing.cast(tuple[set[UserSessionModel], typing.Any], self._client.gets(u_id))
        return False

    @typing.override
    async def invalidate_all(self, u_id: str) -> bool:
        cache, cas = typing.cast(tuple[set[UserSessionModel] | None, typing.Any], self._client.gets(u_id))
        if not cache:
            return True
        invalidated = cache
        for _ in range(
            typing.cast(MemcachedProvider, AppConfig.SESSIONS.PROVIDER_CONFIG).MEMCACHED_RETRIES_BEFORE_FAIL
        ):
            if self._client.cas(u_id, cache.difference(invalidated), cas):
                self._client.delete_many([s.id for s in cache])
                return True
            cache, cas = typing.cast(tuple[set[UserSessionModel], typing.Any], self._client.gets(u_id))
        return False

    @typing.override
    async def delete_old(self, u_id: str, *u_ids: str, only_expired: bool = False, only_invalid: bool = False) -> bool:
        """Delete all old `Sessions` for `Users` with IDs (`u_id`, *`u_ids`).

        This `SESSIONS_PROVIDER` **doesn't** store neither the expired nor the explicitly invalidated `Sessions`,
        so this method only manually cleans up the not-yet-evicted leftover parts of the cache.

        :param bool only_expired:
            Irrelevant and ignored for this `SESSIONS_PROVIDER`.
        :param bool only_invalid:
            Irrelevant and ignored for this `SESSIONS_PROVIDER`.

        :return bool:
            If the `Sessions` deletion was successfull or not.
        """
        cache: dict[_MemcacheKey, set[UserSessionModel]] = self._client.get_many([u_id, *u_ids])
        if not cache:
            return True
        cache = {u_id: UserSessionModel.remove_expired(sessions) for u_id, sessions in cache.items()}
        # TODO: EDGE_CASE: race-condition if one of the users logs-in between .get_many() and .set_many(),
        #       this will delete the new relation created from the log-in,
        #       how to NOT have a separate retires-loop with .cas() for each u_id?
        return not self._client.set_many(cache)
