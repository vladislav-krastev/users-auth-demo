import typing

from config import ProviderConfigREDIS
from utils import logging

from .abstract import BaseSessionsProvider, Session


log = logging.getLogger("uvicorn.error")


class SessionsProviderRedis(BaseSessionsProvider):
    def __init__(self, config: ProviderConfigREDIS) -> None:
        pass

    async def validate_connection(self) -> bool:
        raise NotImplementedError()

    @typing.override
    async def create(self, s: Session) -> bool:
        raise NotImplementedError()

    @typing.override
    async def get(self, u_id: str, s_id: str) -> Session | None:
        raise NotImplementedError()

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
