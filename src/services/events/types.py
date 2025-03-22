import enum
import typing


class EVENT(enum.Enum):
    """An internal `Event`."""


EVENT_DATA = typing.NamedTuple
"""The payload of an internal `Event`."""


EVENT_CALLBACK = typing.Callable[[EVENT, EVENT_DATA], typing.Any]
"""The singture of a callable that can be registered to handle an internal `Event`."""
