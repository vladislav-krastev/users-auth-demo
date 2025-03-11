import typing
from datetime import UTC, datetime

import pydantic

from services.sessions import Session


def NOW() -> float:
    return datetime.now(UTC).timestamp()


class UserSession(typing.TypedDict):
    id: str
    exp: str


class UserSessionsModel(pydantic.BaseModel):
    """ """

    user_id: str
    sessions: list[UserSession] | None

    def update(self, s: Session | None) -> None:
        """ """
        self.sessions = [] if self.sessions is None else [s for s in self.sessions if float(s["exp"]) > NOW()]
        if s:
            self.sessions.append({"id": s.id, "exp": str(s.expires_at.timestamp())})


class SessionModel(pydantic.BaseModel):
    """ """
