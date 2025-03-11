import typing
import uuid
from functools import partial

from config import AppConfig
from config.users import UsersProvider
from utils import exceptions, logging, pagination, singleton

from .models import AdminUser, BaseUser, NormalUser
from .providers import BaseUsersProvider


log = logging.getLogger("users")


# being a Singleton is just a precaution, everything should be using the 'UsersService' instance:
class _UsersService(singleton.Singleton):
    """Service for access to the `Users`."""

    __slots__ = ("_provider",)

    def __init__(self):
        self._provider: BaseUsersProvider = None  # type: ignore

    async def setup(self) -> bool:
        """Setup the `UsersService` global singleton.

        For the service to be considered operational, this method **must** be called
        before anything else and the return value **must** be `True`.

        Is idempotent.

        :return bool:
            If the setup was successfull or not.
        """
        if self._provider is not None:
            return True
        log.info(f"using storage provider: {AppConfig.USERS.PROVIDER}")
        match AppConfig.USERS.PROVIDER:
            case UsersProvider.DYNAMODB:
                from .providers.dynamodb import UsersProviderDynamoDB

                provider = UsersProviderDynamoDB
            case UsersProvider.RDBMS:
                from .providers.rdbms import UsersProviderRDBMS

                provider = UsersProviderRDBMS
        self._provider: BaseUsersProvider = provider(AppConfig.USERS.PROVIDER_CONFIG)  # type: ignore
        return await self._provider.validate_connection()

    async def create[T: BaseUser](self, user: T) -> T | None:
        """Create a new `User`.

        :return T:
            The created `User`.
        :return None:
            When the `User` couldn't be created.
        """
        with log.any_error():
            return await self._provider.create(user)

    # TODO: default value for T when bumped to python 3.13:
    async def get_unique_by[T: BaseUser](
        self,
        as_model: type[T] = BaseUser,
        /,
        *,
        use_OR_clause=False,
        **filters: typing.Any,
    ) -> T | None:
        """Get an existing `User`.

        :param bool use_OR_clause:
            If multiple `filters` are provided and `use_OR_clause` == **True**, they are ORed, else they are ANDed.
            Is a no-op if `filters` has only a single KVP.
        :param filters:
            KVPs on which filtering of the `User` objects is performed. At least one KVP is required.

        :raise FilterMissingError:
            When `filters` is empty.

        :return T:
            An instance of type `as_model` if the `User` was found.
        :return None:
            If the `User` was not found.
        """
        if not filters:
            raise exceptions.FilterMissingError()
        with log.any_error():
            return await self._provider.get_unique_by(
                as_model,
                use_OR_clause=use_OR_clause,
                **filters,
            )

    async def get_many[T: AdminUser | NormalUser](
        self,
        as_model: type[T],
        /,
        offset: int = 0,
        limit: int | None = None,
        *,
        order_by: str = "id",
        order_asc: bool = True,
        use_OR_clause: bool = False,
        **filters: typing.Any,
    ) -> list[T] | None:
        """Get a subset from the list of all `Users`.

        :param bool only_currently_active:
            If **True**, the pages will contain only the `Users` with at least one valid (non-expired) `Session`.

        :param bool use_OR_clause:
            If multiple `filters` are provided and `use_OR_clause` == **True**, they are ORed, else they are ANDed.
            Is a no-op if `filters` is empty or has only a single KVP.

        :return list[T]:
            Could be an empty list (based on this method's filters/page params etc.) - a ***valid*** response.
        :return None:
            When there was some error - treat as an error/***non-valid*** response.
        """
        with log.any_error():
            return await self._provider.get_many(
                as_model,
                offset=offset,
                limit=limit,
                order_by=order_by,
                order_asc=order_asc,
                use_OR_clause=use_OR_clause,
                **filters,
            )

    async def get_all[T: BaseUser](
        self,
        as_model: type[T],
        /,
    ) -> list[T] | None:
        if self._provider.has_support_for_get_all:
            return await self._provider.get_many(
                as_model,
                offset=0,
                limit=None,
                order_by="id",
                order_asc=True,
            )

        getter = partial(self._provider.get_many, as_model, order_by="id", order_asc=True)
        # TODO: instead of wrapping, dynamically determine how to pass the args from within pagination.in_memory_all().
        # i.e are they pos-only and in what order, or are they kwargs. (print(inspect.signature(getter))
        wrapper = lambda offset, limit: (await getter(offset=offset, limit=limit) for _ in "_").__anext__()
        return await pagination.get_in_memory_all(wrapper)

    async def update[T: BaseUser](
        self,
        as_model: type[T] = BaseUser,
        /,
        *,
        user_id: str | uuid.UUID,
        **fields: typing.Any,
    ) -> T | None:
        """Update an existing `User`.

        :return T:
            The updated `User`.
        :return None:
            When the `User` could not be updated. Treat as an error/***non-valid*** response.
        """
        with log.any_error():
            return await self._provider.update(as_model, str(user_id), **fields)

    async def delete(self, user_id: str | uuid.UUID) -> bool:
        """Delete an existing `User`.

        :return bool:
            If the `User` deletion was successfull or not.
        """
        with log.any_error():
            return await self._provider.delete(str(user_id))
        return False

    # async def track_login(self, user: BaseUser, provider: USER_LOGIN_PROVIDER) -> bool:
    #     """ """
    #     with log.any_error():
    #         await self._provider.create_login(user, provider)
    #     return False


UsersService: typing.Final[_UsersService] = _UsersService()
"""Service for access to the `Users`."""
