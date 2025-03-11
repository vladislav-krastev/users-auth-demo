"""Custom logger."""

import contextlib
import inspect
import logging as _l
import typing

import uvicorn.logging


class _FormatterINFO(uvicorn.logging.ColourizedFormatter):
    def __init__(self, prefix: str | None = None):
        fmt = "%(levelprefix)s " + (f"{prefix} " if prefix else "") + "%(message)s"
        super().__init__(fmt=fmt)


class _FormatterERROR(uvicorn.logging.ColourizedFormatter):
    def __init__(self, prefix: str | None = None):
        fmt = (
            "%(levelprefix)s "
            + (f"{prefix} " if prefix else "")
            +
            # "%(funcName)s %(args)s: %(message)s"  # TODO
            "%(funcName)s: %(message)s"
        )
        super().__init__(fmt=fmt)


class _StreamHandlerINFO(_l.StreamHandler):
    def __init__(self, name: str | None = None):
        super().__init__()
        self.setLevel("INFO")
        self.setFormatter(_FormatterINFO(name))
        self.addFilter(lambda r: r.levelno < _l.ERROR)


class _StreamHandlerERROR(_l.StreamHandler):
    def __init__(self, name: str | None = None):
        super().__init__()
        self.setLevel("ERROR")
        self.setFormatter(_FormatterERROR(name))


class _PrefixHandler(_l.Handler):
    def __init__(self, prefix: str):
        super().__init__(level=_l.DEBUG)
        self.prefix = prefix

    @typing.override
    def emit(self, record: _l.LogRecord) -> None:
        record.msg = f"{self.prefix} {record.msg}"


_DEFAULT_LOGGER_NAME: typing.Final[str] = "users_auth"


class CustomLogger(_l.Logger):
    """Simple custom Logger.

    Provides couple of simple custom handlers and formatters.\n
    Provides couple of utilities for ease of life (see .any_error() and .with_prefix()).\n
    Pre-pends the log messages with the formatted name of the logger, e.g.: "logger-name your-msg".

    Otherwise, identical interface and full interoperability with the built-in `logging.Logger` class.
    """

    def __new__(cls, name: str | None = None) -> typing.Self:
        if name:
            logger = _l.getLogger(_DEFAULT_LOGGER_NAME).getChild(name)
            if not logger.handlers:
                logger.addHandler(_StreamHandlerINFO(name))
                logger.addHandler(_StreamHandlerERROR(name))
                logger.propagate = False
        else:
            logger = _l.getLogger(_DEFAULT_LOGGER_NAME)
        logger.__class__ = cls
        return typing.cast(cls, logger)  # type: ignore

    def __init__(self, name: str | None = None) -> None: ...

    @typing.override
    def getChild(self, suffix):
        suffix = f"[{suffix.upper()}]"
        child = super().getChild(suffix)
        if not child.handlers:
            child.addHandler(_StreamHandlerINFO(suffix))
            child.addHandler(_StreamHandlerERROR(suffix))
            child.propagate = False
            child.__class__ = type(self)
        return child

    @contextlib.contextmanager
    def with_prefix(self, prefix: str | None = None):
        """Pre-prend any log messages emitted from **self** within the current context with `prefix`.

        Leaving `prefix` as **None** is a no-op.
        """
        # TODO: thread-safe
        try:
            if prefix:
                new_h = _PrefixHandler(prefix)
                self.handlers.insert(0, new_h)
            yield
        finally:
            if prefix:
                self.handlers.pop(self.handlers.index(new_h))

    @contextlib.contextmanager
    def any_error(self, *, reraise=False, exit_code: int | None = None) -> typing.Generator[None, typing.Any, None]:
        """Capture and auto-log any raised exception.

        The logged error msg will try including the `locals` of this method's caller.

        :param bool reraise:
            Should the captured exception be re-raised.

        :param bool exit_code:
            If not **None**, `sys.exit()` is called with the provided `exit_code`.

        When both `reraise` and `exit_code` are present, `reraise` takes precedence and `exit_code` is a no-op.
        """
        try:
            yield
        except Exception as err:
            # TODO: attach trace for own callers, e.g. 'API-endpoint -> service-method',
            #       instead of only 'service-method'. Will require a way for an understandable msg format.
            # TODO: fuller exception info, instead of only exception msg?
            try:
                current_frame = inspect.currentframe()
                assert (
                    current_frame is not None
                    and current_frame.f_back is not None
                    and current_frame.f_back.f_back is not None
                )
                caller_locals = {k: v for k, v in current_frame.f_back.f_back.f_locals.items() if k not in ("self",)}
            except AssertionError:
                caller_locals = {}
            self.error(err, caller_locals, stacklevel=3)
            if reraise:
                raise err
            if exit_code:
                exit(exit_code)


_DEFAULT_LOGGER: typing.Final[CustomLogger] = CustomLogger()
_DEFAULT_LOGGER.addHandler(_StreamHandlerINFO())
_DEFAULT_LOGGER.addHandler(_StreamHandlerERROR())
_DEFAULT_LOGGER.propagate = False
_DEFAULT_LOGGER.setLevel(_l.DEBUG)


def getLogger(name: str | None = None) -> CustomLogger:
    """Return a `CustomLogger` with the specified `name`, creating it if necessary.

    Same name and signature as `logging.getLogger()` for easy find-and-replace, if needed.

    If no `name` is specified, return the root logger.\n
    If `name` is specified, it will be used as the prefix for each log-message.
    """
    return CustomLogger(name) if name else _DEFAULT_LOGGER
