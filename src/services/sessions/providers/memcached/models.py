import typing
from datetime import UTC, datetime


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
