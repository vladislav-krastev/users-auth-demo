import enum
from collections import defaultdict


@enum.unique
class WebHookEvent(enum.Enum):
    """An internal `Event` that a `WebHook` can subscribe to."""

    USER_REGISTER = ""
    USER_LOGIN_LOCAL = ""
    USER_LOGIN_EXTERNAL = ""
    USER_LOGOUT = ""
    USER_UPDATED = ""
    USER_DELETED = ""


subscriptions = defaultdict(list)


def subscribe(event_type: str, fn):
    subscriptions[event_type].append(fn)
