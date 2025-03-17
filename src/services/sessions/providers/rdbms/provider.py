import typing
from datetime import UTC, datetime

import sqlalchemy as sa
import sqlalchemy.ext.asyncio as sa_async

from config.sessions import RDBMSProviderConfig
from utils import logging

from ..abstract import BaseSessionsProvider, Session
from .models import SessionModel


log = logging.getLogger("sessions-rdbms")


def NOW() -> datetime:
    return datetime.now(UTC)


class SessionsProviderRDBMS(BaseSessionsProvider):
    """ """

    __slots__ = ("_connection_url", "_db")

    def __init__(self, config: RDBMSProviderConfig) -> None:
        engine = sa_async.create_async_engine(
            config.CONNECTION_URL.unicode_string(),
            echo=config.ECHO_SQL,
            pool_pre_ping=True,
        )
        self.__connection_url = engine.url
        self._db = sa_async.async_sessionmaker(engine, class_=sa_async.AsyncSession, expire_on_commit=False)

    @typing.override
    async def validate_connection(self) -> bool:
        try:
            async with self._db() as db:
                assert len((await db.execute(sa.text("SELECT 1;"))).all()) == 1
        except Exception as err:
            log.error(f"Could not establish connection to {self.__connection_url}: {err}")
            return False
        log.info(f"established connection to {self.__connection_url}")
        return True

    @typing.override
    async def create(self, s: Session) -> Session | None:
        # expr = sa.insert(SessionModel).values(**s.model_dump(exclude={"id"})).returning(SessionModel)
        expr = sa.insert(SessionModel).values(**s.model_dump(exclude={"is_expired"})).returning(SessionModel)
        async with self._db() as db, db.begin():
            return Session.model_validate((await db.scalars(expr)).one(), from_attributes=True)
        return None

    @typing.override
    async def get(self, u_id: str, s_id: str) -> Session | None:
        expr = sa.select(SessionModel).where(
            SessionModel.is_valid.is_(True)
            & (SessionModel.expires_at > NOW())
            & (SessionModel.id == s_id)
            & (SessionModel.user_id == u_id)
        )
        async with self._db() as db:
            return Session.model_validate((await db.scalars(expr)).one(), from_attributes=True)
        return None

    @typing.override
    async def get_many(
        self, u_id: str, *u_ids: str, offset: int, limit: int | None, include_expired: bool
    ) -> list[Session]:
        expr = (
            sa.select(SessionModel)
            .where(sa.column(SessionModel.user_id.key).in_((u_id, *u_ids)) if u_ids else SessionModel.user_id == u_id)
            .order_by(SessionModel.user_id, SessionModel.created_at)
            .offset(offset)
            .limit(limit)
        )
        if not include_expired:
            expr = expr.where(SessionModel.is_valid.is_(True) & (SessionModel.expires_at > NOW()))
        async with self._db() as db:
            res = (await db.scalars(expr)).all()
        return [] if len(res) == 0 else [Session.model_validate(i, from_attributes=True) for i in res]

    @typing.override
    async def invalidate(self, u_id: str, s_id: str) -> bool:
        expr = (
            sa.update(SessionModel)
            .where(SessionModel.is_valid.is_(True) & (SessionModel.id == s_id) & (SessionModel.user_id == u_id))
            .values(is_valid=False)
            .returning(SessionModel)
        )
        async with self._db() as db, db.begin():
            (await db.scalars(expr)).one()
            return True
        return False

    @typing.override
    async def invalidate_all(self, u_id: str) -> list[str] | None:
        expr = (
            sa.update(SessionModel)
            .where(SessionModel.is_valid.is_(True) & (SessionModel.user_id == u_id))
            .values(is_valid=False)
            .returning(SessionModel)
        )
        async with self._db() as db, db.begin():
            res = (await db.scalars(expr)).all()
            return [s.id for s in res]

    @typing.override
    async def delete_old(self, u_id: str, *u_ids: str, only_expired: bool = False, only_invalid: bool = False) -> bool:
        expr = sa.delete(SessionModel).where(
            sa.column(SessionModel.user_id.key).in_((u_id, *u_ids)) if u_ids else SessionModel.user_id == u_id
        )
        if (only_invalid and only_expired) or not (only_invalid or only_expired):
            expr = expr.where(sa.or_(SessionModel.is_valid.is_(False), SessionModel.expires_at < NOW()))
        elif only_invalid:
            expr = expr.where(SessionModel.is_valid.is_(False))
        else:  # only_expired
            expr = expr.where(SessionModel.is_valid.is_(True) & (SessionModel.expires_at < NOW()))
        async with self._db() as db, db.begin():
            await db.execute(expr)
            return True
        return False
