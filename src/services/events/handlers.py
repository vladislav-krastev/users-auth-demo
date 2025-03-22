import typing

from utils import exceptions, logging

from .events import SESSION_EVENT, USER_EVENT
from .types import EVENT, EVENT_CALLBACK, EVENT_DATA


log = logging.getLogger()


def log_handler(event: EVENT, value: EVENT_DATA) -> None:
    match event:
        case USER_EVENT.REGISTER:
            value = typing.cast(USER_EVENT.REGISTER.value, value)
            log.info(f"Registered User(ID={value.user_id} USERNAME={value.username})")
        case USER_EVENT.UPDATE:
            value = typing.cast(USER_EVENT.UPDATE.value, value)
            log.info(f"Updated '{value.fields}' for User(ID={value.user_id})")
        case USER_EVENT.UPDATE_PASSWORD:
            value = typing.cast(USER_EVENT.UPDATE_PASSWORD.value, value)
            log.info(f"Updated 'password' for User(ID={value.user_id})")
        case USER_EVENT.DELETE:
            value = typing.cast(USER_EVENT.DELETE.value, value)
            log.info(f"Deleted User(ID={value.user_id})")
        case SESSION_EVENT.LOGIN:
            value = typing.cast(SESSION_EVENT.LOGIN.value, value)
            log.info(
                f"Logged-in User(ID={value.user_id}) with Session(ID={value.session_id} PROVIDER={value.provider} TYPE={value.type})"
            )
        case SESSION_EVENT.LOGOUT:
            value = typing.cast(SESSION_EVENT.LOGOUT.value, value)
            log.info(f"Logged-out User(ID={value.user_id}) with Session(ID={value.session_id})")
        case _:
            raise exceptions.InvalidEventError(log_handler.__name__, event)


def init_log_handler(
    register_events: typing.Callable[[EVENT | typing.Iterable[EVENT], EVENT_CALLBACK], typing.Any],
) -> None:
    register_events(
        (
            USER_EVENT.REGISTER,
            USER_EVENT.UPDATE,
            USER_EVENT.UPDATE_PASSWORD,
            USER_EVENT.DELETE,
            SESSION_EVENT.LOGIN,
            SESSION_EVENT.LOGOUT,
        ),
        log_handler,
    )
