import typing

from .types import EVENT, EVENT_DATA


class _RegisterEvent(EVENT_DATA):
    user_id: str
    username: str


class _UpdateEvent(EVENT_DATA):
    user_id: str
    fields: typing.Iterable[str]


class _UpdatePasswordEvent(EVENT_DATA):
    user_id: str


class _DeleteEvent(EVENT_DATA):
    user_id: str


class _LoginEvent(EVENT_DATA):
    user_id: str
    session_id: str
    provider: str
    type: str


class _LogoutEvent(EVENT_DATA):
    user_id: str
    session_id: str


class USER_EVENT(EVENT):
    """`User` events."""

    REGISTER = _RegisterEvent
    UPDATE = _UpdateEvent
    UPDATE_PASSWORD = _UpdatePasswordEvent
    DELETE = _DeleteEvent


class SESSION_EVENT(EVENT):
    """`Session` events."""

    LOGIN = _LoginEvent
    LOGOUT = _LogoutEvent
