import typing
import uuid
from datetime import UTC, datetime, timedelta

from config import AppConfig
from services.sessions import Session
from services.sessions.types import SESSION_PROVIDER, SESSION_TYPE

from .types import CACHED_SESSION


def NOW() -> int:
    return int(datetime.now(UTC).replace(microsecond=0).timestamp())


class UserSessionModel(typing.NamedTuple):
    """Represents the relation between a `User` and a `Session`.

    Used to locate all the `Sessions` for a `User`.
    """

    id: str
    exp: str

    @staticmethod
    def remove_expired(sessions: typing.Iterable["UserSessionModel"]) -> set["UserSessionModel"]:
        """Filter provided `sessions` to a new set, containg only non-expired `UserSessionModel` instances."""
        now = NOW()
        return {s for s in sessions if int(s.exp) > now}


class SessionModel(typing.NamedTuple):
    """A (mem-)cached representation of an internal `Session`."""

    s_id: str
    u_id: str
    expires_at: int
    provider: SESSION_PROVIDER
    type: SESSION_TYPE

    @staticmethod
    def from_internal(s: Session) -> "SessionModel":
        return SessionModel(
            s.id,
            str(s.user_id),
            int(s.expires_at.timestamp()),
            s.provider,
            s.type,
        )

    def to_internal(self) -> Session:
        expires_at = datetime.fromtimestamp(self.expires_at, UTC).replace(microsecond=0)
        if self.provider == "local":
            expires_delta = (
                AppConfig.LOCAL_AUTH.COOKIE.EXPIRE_MINUTES
                if self.type == "cookie"
                else AppConfig.LOCAL_AUTH.ACCESS_TOKEN.EXPIRE_MINUTES
            )
        else:
            expires_delta = AppConfig.OAUTH2.config_for(self.provider).ACCESS_TOKEN_EXPIRE_MINUTES
        return Session(
            id=self.s_id,
            user_id=uuid.UUID(self.u_id),
            is_valid=True,
            created_at=expires_at - timedelta(minutes=expires_delta),
            expires_at=expires_at,
            provider=self.provider,
            type=self.type,
        )

    @staticmethod
    def from_cache(cache: CACHED_SESSION) -> "SessionModel":
        cached_provider, cached_type = cache[3].split("-")
        return SessionModel(
            cache[0],
            cache[1],
            int(cache[2]),
            cached_provider,  # type: ignore
            "cookie" if cached_type == "c" else "token",
        )

    def to_cache(self) -> CACHED_SESSION:
        return (
            self.s_id,
            self.u_id,
            str(self.expires_at),
            f"{self.provider}-{'c' if self.type == 'cookie' else 't'}",
        )
