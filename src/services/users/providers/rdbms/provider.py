import typing
from datetime import datetime

import sqlalchemy as sa
import sqlalchemy.ext.asyncio as sa_async
import sqlalchemy.orm as sa_orm

from config.users import RDBMSProvider
from utils import exceptions, logging

from ...types import USER_LOGIN_PROVIDER
from ..abstract import BaseUser, BaseUsersProvider
from .models import UserLoginModel, UserModel


log = logging.getLogger("users-rdbms")


def is_iterable(x: typing.Any):
    """Try to determine if `x` is an Iterable.

    A string is considered a non-iterable.
    """
    if hasattr(x, "__iter__"):
        return not isinstance(x, (type, str))
    if hasattr(x, "__getitem__"):
        try:
            x[0]
            return True
        except Exception:
            return False
    return False


class UsersProviderRDBMS(BaseUsersProvider):
    """ """

    __slots__ = ("_connection_url", "_db")

    has_support_for_get_all = True

    def __init__(self, config: RDBMSProvider) -> None:
        engine = sa_async.create_async_engine(
            config.DB_CONNECT_URL.unicode_string(),
            echo=config.ECHO_SQL,
            pool_pre_ping=True,
        )
        self._connection_url = engine.url
        self._db = sa_async.async_sessionmaker(engine, class_=sa_async.AsyncSession, expire_on_commit=False)

    @typing.override
    async def validate_connection(self) -> bool:
        try:
            async with self._db() as db:
                assert len((await db.execute(sa.text("SELECT 1;"))).all()) == 1
        except Exception as err:
            log.error(f"Could not establish connection to: {self._connection_url}: {err}")
            return False
        log.info(f"established connection to: {self._connection_url}")
        return True

    @typing.override
    async def create[T: BaseUser](self, u: T) -> T | None:
        expr = sa.insert(UserModel).values(**u.model_dump(exclude={"id", "logins_from"})).returning(UserModel)
        async with self._db() as db, db.begin():
            res = (await db.scalars(expr)).unique().one()
        return u.__class__.model_validate(res, from_attributes=True)

    @typing.override
    async def get_unique_by[T: BaseUser](
        self, model: type[T], /, *, use_OR_clause=False, **filters: typing.Any
    ) -> T | None:
        if not filters:
            return None
        expr = (
            sa.select(UserModel)
            # .join(UserModel.logins)
            # .options(sa_orm.contains_eager(UserModel.logins))
        )
        is_deleted: bool | None = filters.pop(UserModel.is_deleted.key, False)  # NONE includes both
        if is_deleted is not None:
            expr = expr.where(UserModel.is_deleted.is_(is_deleted))
        filter_expr = []
        for k, v in filters.items():
            if is_iterable(v):
                raise exceptions.FilterNotAllowedError(k, v)
            filter_expr.append(getattr(UserModel, k) == v)
        expr = expr.where((sa.or_ if use_OR_clause else sa.and_)(*filter_expr)).limit(2)
        async with self._db() as db:
            res = (await db.scalars(expr)).unique().all()
        if len(res) == 2:
            raise exceptions.FilterNotUniqueError(UserModel, "OR" if use_OR_clause else "AND", **filters)
        return None if len(res) == 0 else res[0].to_internal(model)

    @typing.override
    async def get_many[T: BaseUser](
        self,
        model: type[T],
        /,
        *,
        offset: int,
        limit: int | None,
        order_by: str,
        order_asc: bool,
        use_OR_clause=False,
        **filters: typing.Any,
    ) -> list[T]:
        order_by_attr = getattr(UserModel, order_by)
        print(offset)
        print(limit)
        expr = (
            sa.select(UserModel)
            .where(UserModel.is_admin.is_(model.model_fields["is_admin"].default))
            .offset(offset)
            .limit(limit)
            .order_by(order_by_attr if order_asc else sa.desc(order_by_attr))
        )
        is_deleted: bool | None = filters.pop(UserModel.is_deleted.key, False)  # NONE includes both
        if is_deleted is not None:
            expr = expr.where(UserModel.is_deleted.is_(is_deleted))
        if filters:
            expr = expr.where(
                (sa.or_ if use_OR_clause else sa.and_)(
                    *[
                        sa.column(getattr(UserModel, k).key).in_(v) if is_iterable(v) else getattr(UserModel, k) == v
                        for k, v in filters.items()
                    ]
                )
            )
        async with self._db() as db:
            return [r.to_internal(model) for r in (await db.scalars(expr)).unique().all()]

    @typing.override
    async def update[T: BaseUser](self, model: type[T], /, u_id: str, **kwargs) -> T | None:
        expr = sa.select_for
        expr = (
            sa.update(UserModel)
            .where(UserModel.is_deleted.is_(False) & (UserModel.id == u_id))
            .values(kwargs)
            .returning(UserModel)
        )
        async with self._db() as db, db.begin():
            return (await db.scalars(expr)).one().to_internal(model)

    @typing.override
    async def delete(self, u_id: str) -> bool:
        expr = (
            sa.update(UserModel)
            .where(UserModel.is_deleted.is_(False) & (UserModel.id == u_id))
            .values(password=None, is_deleted=True, deleted_at=datetime.now())
            .returning(UserModel)
        )
        async with self._db() as db, db.begin():
            (await db.scalars(expr)).one()
            return True
        return False

    async def create_login(self, user: BaseUser, provider: USER_LOGIN_PROVIDER) -> bool:
        """ """
        expr = sa.insert(UserLoginModel).values(user_id=user.id, provider=provider).returning(UserLoginModel)
        async with self._db() as db, db.begin():
            (await db.scalars(expr)).one()
            return True
        return False

    async def get_logins_count(self, *providers: USER_LOGIN_PROVIDER) -> dict[USER_LOGIN_PROVIDER, int]:
        """ """
        expr = sa.select(UserLoginModel.provider, sa.func.count()).group_by(UserLoginModel.provider)
        if providers:
            expr = expr.where(
                UserLoginModel.provider == providers[0]
                if len(providers) == 1
                else UserLoginModel.provider.in_(providers)
            )
        async with self._db() as db:
            return {r[0]: r[1] for r in (await db.execute(expr)).all()}

    async def get_logins_for_provider[T: BaseUser](
        self, model: type[T], /, provider: USER_LOGIN_PROVIDER, *, offset: int, limit: int
    ) -> list[T]:
        """ """
        expr = (
            sa.select(UserModel)
            .join(UserModel.logins)
            .options(sa_orm.contains_eager(UserModel.logins))
            .where(UserLoginModel.provider == provider)
            .offset(offset)
            .limit(limit)
        )
        async with self._db() as db:
            return [r.to_internal(model) for r in (await db.scalars(expr)).unique().all()]
