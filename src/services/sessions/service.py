import asyncio
import typing
import uuid
from datetime import UTC, datetime

from config import AppConfig
from config.sessions import SessionsProvider
from services.users import BaseUser
from utils import logging, singleton

from .models import Session
from .providers import BaseSessionsProvider


log = logging.getLogger("sessions")


# being a Singleton is just a precaution, everything should be using the 'SessionsService' instance:
class _SessionsService(singleton.Singleton):
    """Service for access to the `Sessions` of a `User`."""

    __slots__ = ("_provider",)

    def __init__(self):
        self._provider: BaseSessionsProvider = None  # type: ignore

    async def setup(self) -> bool:
        """Setup the `SessionsService` global singleton.

        For the service to be considered operational, this method **must** be called
        before anything else and the return value **must** be `True`.

        Is idempotent.

        :return bool:
            If the setup was successfull or not.
        """
        log.info(f"using storage provider: {AppConfig.SESSIONS.PROVIDER}")
        match AppConfig.SESSIONS.PROVIDER:
            case SessionsProvider.DYNAMODB:
                from .providers.dynamodb import SessionsProviderDynamoDB

                provider = SessionsProviderDynamoDB
            case SessionsProvider.MEMCACHED:
                from .providers.memcached import SessionsProviderMemcached

                provider = SessionsProviderMemcached
            case SessionsProvider.RDBMS:
                from .providers.rdbms import SessionsProviderRDBMS

                provider = SessionsProviderRDBMS
            case SessionsProvider.REDIS:
                from .providers.redis import SessionsProviderRedis

                provider = SessionsProviderRedis
        self._provider: BaseSessionsProvider = provider(AppConfig.SESSIONS.PROVIDER_CONFIG)  # type: ignore
        return await self._provider.validate_connection()

    async def filter_out_inactive[T: str | uuid.UUID | BaseUser](self, users: list[T]) -> list[T]:
        """Return the subset from `users` representing only the currently logged-in `Users`."""
        if not users:
            return []
        u_ids = (
            typing.cast(list[str], users)
            if isinstance(users[0], str)
            else [str(u) for u in users]
            if isinstance(users[0], uuid.UUID)
            else [str(typing.cast(BaseUser, u).id) for u in users]
        )
        with log.any_error():
            sessions = await self._provider.get_many(*u_ids, offset=0, limit=None, include_expired=False)
            u_ids = set(s.user_id for s in sessions)
        if _failed_session_invalidations:
            asyncio.create_task(_fsi_clean_up())
        return (
            typing.cast(list[T], [str(u_id) for u_id in u_ids])
            if isinstance(users[0], str)
            else list(filter(lambda u: u in u_ids, users))
            if isinstance(users[0], uuid.UUID)
            else list(filter(lambda u: typing.cast(BaseUser, u).id in u_ids, users))
        )

    async def create(self, s: Session) -> Session | None:
        """Create a new `Session`.

        :return:
            The created `Session`.
        :return None:
            When the `Session` couldn't be created.
        """
        with log.any_error():
            res = await self._provider.create(s)
            if _failed_session_invalidations:
                asyncio.create_task(_fsi_clean_up())
            return res
        return None

    async def get(
        self,
        user_id: str | uuid.UUID,
        session_id: str,
    ) -> Session | None:
        """Get the `Session` with ID `session_id` for the `User` with ID `user_id`."""
        with log.any_error():
            res = await self._provider.get(str(user_id), session_id)
            if _failed_session_invalidations:
                asyncio.create_task(_fsi_clean_up())
            return res

    async def get_many(
        self,
        user_id: str | uuid.UUID,
        *user_ids: str | uuid.UUID,
        offset: int,
        limit: int,
        include_expired: bool = False,
    ) -> list[Session] | None:
        """ """
        with log.any_error():
            res = await self._provider.get_many(
                str(user_id),
                *[str(u_id) for u_id in user_ids],
                offset=offset,
                limit=limit,
                include_expired=include_expired,
            )
            if _failed_session_invalidations:
                asyncio.create_task(_fsi_clean_up())
            return res

    async def invalidate(
        self,
        user_id: str | uuid.UUID,
        session_id: str,
    ) -> bool:
        """Invalidate the `Session` with ID `session_id` for the `User` with ID `user_id`.

        :return bool:
            If the `Session` invalidation was successfull or not.
        """
        with log.any_error():
            try:
                res = await self._provider.invalidate(str(user_id), session_id)
                if _failed_session_invalidations:
                    asyncio.create_task(_fsi_clean_up())
                return res
            except Exception as err:
                _failed_session_invalidations.append(
                    _FSI(
                        user_id=str(user_id),
                        session_id=session_id,
                        failure_timestamp=int(datetime.now(UTC).timestamp()),
                    )
                )
                raise err

    async def invalidate_all(
        self,
        user_id: str | uuid.UUID,
    ) -> list[str] | None:
        """Invalidate all `Sessions` of the `User` with ID `user_id`.

        :return list:
            The IDs of all invalidated `Sessions`.
        """
        with log.any_error():
            try:
                res = await self._provider.invalidate_all(str(user_id))
                if _failed_session_invalidations:
                    asyncio.create_task(_fsi_clean_up())
                return res
            except Exception as err:
                _failed_session_invalidations.append(
                    _FSI(
                        user_id=str(user_id),
                        session_id=None,
                        failure_timestamp=int(datetime.now(UTC).timestamp()),
                    )
                )
                raise err

    async def util_delete_old(
        self,
        user_id: str | uuid.UUID,
        *user_ids: str | uuid.UUID,
        force_expired: bool = True,
        force_invalid: bool = True,
    ) -> bool:
        """Utility for making sure old (expired and/or invalid) `Sessions` are deleted."""
        with log.any_error():
            return await self._provider.delete_old(
                str(user_id), *[str(id_) for id_ in user_ids], only_expired=force_expired, only_invalid=force_invalid
            )
        # TODO: should we check for _failed_session_invalidations, if this would be ran manually?


SessionsService: typing.Final[_SessionsService] = _SessionsService()
"""Service for access to the `Sessions` of a `User`."""


# TODO: at the very least - external storage/cache, accessible by all of the replicas of the app:
class _FSI:
    """A failed `Session` invalidation."""

    def __init__(self, user_id: str, session_id: str | None, failure_timestamp: int):
        self.user_id = user_id
        self.session_id = session_id
        self.last_failure_timestamp = failure_timestamp
        self.failure_count = 1


_failed_session_invalidations: list[_FSI] = []


async def _fsi_clean_up() -> None:
    with log.with_prefix("[FSI-CLEANUP]"):
        for i, fsi in enumerate(_failed_session_invalidations[:]):
            if fsi.session_id is None:
                msg = f"Failed invalidating all sessions for user (user_id={fsi.user_id})\n"
                is_success = await SessionsService.invalidate_all(fsi.user_id)
            else:
                msg = f"Failed invalidating session (user_id={fsi.user_id}, session_id={fsi.session_id})\n"
                is_success = await SessionsService.invalidate(fsi.user_id, fsi.session_id)
            if is_success:
                _failed_session_invalidations.pop(i)
            else:
                log.error(
                    msg + f"Last fail at: {datetime.fromtimestamp(fsi.last_failure_timestamp, UTC)}"
                    f"Total fails: {fsi.failure_count}\t"
                )
                fsi.last_failure_timestamp = int(datetime.now(UTC).timestamp())
