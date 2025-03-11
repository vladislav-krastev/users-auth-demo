from datetime import datetime, timezone
from typing import TypeVar

from config import AppConfig


DatetimeOrNone = TypeVar("DatetimeOrNone", datetime, None)
StringOrNone = TypeVar("StringOrNone", str, None)


def datetime_has_timezone_utc(cls_name: str, f_name: str, v: DatetimeOrNone) -> DatetimeOrNone:
    """Validate an instance attribute of type `datetime` has a TZ == UTC."""
    if v is not None and (v.tzinfo is None or v.tzinfo != timezone.utc):
        raise ValueError(f"{cls_name}.{f_name} must always have its TZ set to UTC, received '{v.tzinfo}'")
    return v


def username_is_not_forbidden(username: StringOrNone) -> StringOrNone:
    """Validate the `username` is not a forbidden value."""
    if username is not None and username in AppConfig.USERS.USERNAME_FORBIDDEN:
        raise ValueError(f"Forbidden value for USERNAME: {username}")
    return username
