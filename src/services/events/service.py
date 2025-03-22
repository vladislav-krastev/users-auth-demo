import typing
from collections import defaultdict

from utils import singleton

from .handlers import init_log_handler
from .types import EVENT, EVENT_CALLBACK, EVENT_DATA


# being a Singleton is just a precaution, everything should be using the 'SessionsService' instance:
class _EventsService(singleton.Singleton):
    """Service for emitting and receiving internal `Events`."""

    __slots__ = ()

    __subscriptions: dict[EVENT, set[EVENT_CALLBACK]] = defaultdict(set)

    @classmethod
    async def setup(cls) -> bool:
        init_log_handler(cls.schedule)
        return True

    @classmethod
    def schedule(cls, event: EVENT | typing.Iterable[EVENT], cb: EVENT_CALLBACK) -> None:
        """Schedule a callable execution when one or more `Events` are emiited.

        :param event:
            The `Events` that will trigger the execution of the callback.
            If it's an iterable, it's treated as a set(), i.e. duplicated `Events` are ignored.
        :param cb:
            The callback to execute.
        """
        if isinstance(event, EVENT):
            cls.__subscriptions[event].add(cb)
        else:
            for e in event:
                cls.__subscriptions[e].add(cb)

    @classmethod
    def emit(cls, event: EVENT, values: EVENT_DATA | typing.Iterable[EVENT_DATA]) -> None:
        """Emit an `Event` with one or more values.

        :param event:
            The `Event` to emit.
        :param value:
            One or more values/payloads/bodies of the `event`.
            Each registered event-listener for the `event` will be called with each of the provided `values`.
        """
        if isinstance(values, tuple):
            values = (values,)  # type: ignore
        for cb in cls.__subscriptions.get(event, []):
            for v in values:
                cb(event, v)


EventsService: typing.Final[_EventsService] = _EventsService()
"""Service for emitting and receiving internal `Events`."""
