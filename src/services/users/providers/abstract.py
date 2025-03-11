import typing
from abc import ABC, abstractmethod

from ..models import BaseUser


class BaseUsersProvider(ABC):
    """Base class for a `Users` provider."""

    __slots__ = ()

    has_support_for_get_all: typing.ClassVar[bool]

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate the connection to the `Users` provider."""

    @abstractmethod
    async def create[T: BaseUser](self, u: T) -> T | None:
        """Create a new `User`."""

    @abstractmethod
    async def get_unique_by[T: BaseUser](
        self,
        model: type[T],
        /,
        *,
        use_OR_clause=False,
        **filters: typing.Any,
    ) -> T | None:
        """Get an existing `User`."""

    @abstractmethod
    async def get_many[T: BaseUser](
        self,
        model: type[T],
        /,
        *,
        offset: int,
        limit: int | None,
        order_by: str,
        order_asc: bool,
        **filters: typing.Any,
    ) -> list[T]:
        """Get a subset from the list of all `Users`."""

    @abstractmethod
    async def update[T: BaseUser](self, model: type[T], /, u_id: str, **kwargs) -> T | None:
        """Update an existing `User`."""

    @abstractmethod
    async def delete(self, u_id: str) -> bool:
        """Delete an existing `User`.

        A storage backend may choose to implement "soft" delete, if it supports it.
        """

    # @abstractmethod
    # async def create_login(self, user: BaseUser, provider: USER_LOGIN_PROVIDER) -> bool:
    #     """Recording a new `User` log-in."""
