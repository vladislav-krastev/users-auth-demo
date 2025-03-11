import typing

import pydantic


__all__ = (
    "Singleton",
    "SingletonPydantic",
)


class __SingletonMeta(type):
    __d = {}

    @typing.override
    def __call__(cls):
        mcls = type(cls)
        if cls not in mcls.__d:
            i = cls.__new__(cls)  # type: ignore
            i.__init__()
            mcls.__d[cls] = i
        return mcls.__d[cls]


class Singleton(metaclass=__SingletonMeta):
    """Affects current and all child classes (each will be a separate `Singleton`).

    Only works for classes that don't have constructor args and kwargs.

    Provides the `__slots__` attribute.
    """

    __slots__ = ()


class __SingletonMetaPydantic(type(pydantic.BaseModel)):  # type: ignore
    __d = {}

    def __call__(cls):  # type: ignore
        mcls = type(cls)
        if cls not in mcls.__d:
            i = cls.__new__(cls)  # type: ignore
            i.__init__()
            mcls.__d[cls] = i
        return mcls.__d[cls]


class SingletonPydantic(metaclass=__SingletonMetaPydantic):
    """Affects current and all child classes (each will be a separate `Singleton`).

    Inherit together with `pydantic.BaseModel` or `pydantic_settings.BaseSettings`.

    Only works for models that **don't** need setting their values on instantiation, e.g:
    - a `pydantic.BaseModel` with default values for all fields
    - a `pydantic_settings.BaseSettings` that reads all of its fields from an *.env* file, etc.
    """
