from abc import ABC, abstractmethod

from ..models import Session


class SessionsProviderConnectionError(Exception):
    def __init__(self, provider, err, **details):
        return super().__init__(
            f"Could not connect to Sessions provider: provider = {provider}, details = , error = {err}"
        )


class BaseSessionsProvider(ABC):
    """Base class for a user `Sessions` provider."""

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate the connection to the `Sessions` provider."""

    @abstractmethod
    async def create(self, s: Session) -> Session | None:
        """Create a new `Session`."""

    @abstractmethod
    async def get(self, u_id: str, s_id: str) -> Session | None:
        """Get the `Session` with ID `s_id` for the `User` with ID `u_id`."""

    @abstractmethod
    async def get_many(
        self, u_id: str, *u_ids: str, offset: int, limit: int | None, include_expired: bool
    ) -> list[Session]:
        """Get all `Sessions` for the `Users` with IDs (`u_id`, *`u_ids`)."""

    @abstractmethod
    async def invalidate(self, u_id: str, s_id: str) -> bool:
        """Invalidate the `Session` with ID `s_id` for the `User` with ID `u_id`."""

    @abstractmethod
    async def invalidate_all(self, u_id: str) -> list[str] | None:
        """Invalidate all `Sessions` for the `User` with ID `u_id`."""

    @abstractmethod
    async def delete_old(self, u_id: str, *u_ids: str, only_expired: bool = False, only_invalid: bool = False) -> bool:
        """Delete all old (invalid and/or expired) `Sessions` for `Users` with IDs (`u_id`, *`u_ids`).

        :param bool only_expired:
            Delete only the expired (non-explicitly logged-out) `Sessions`.
        :param bool only_invalid:
            Delete only the explicitly logged-out `Sessions` (which may include `Sessions` that are also already expired).

        If both `only_invalid` and `only_expired` are **True** or if both are **False** - all selected `Sessions` are deleted.

        :return bool:
            If the `Sessions` deletion was successfull or not.
        """
