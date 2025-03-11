import inspect
from abc import ABC
from functools import cache
from typing import TYPE_CHECKING, Any, Callable, Self, cast, final, override

from pydantic import BaseModel as pydantic_BaseModel
from pydantic.fields import FieldInfo as pydantic_FieldInfo


__all__ = [
    "InvalidFieldFactoryError",
    "InvalidMetadataTypeError",
    "make_field_extender",
    "EnchancedModelMixin",
    "BaseFieldMeta",
    "make_field_with_meta",
]


class InvalidFieldFactoryError(ValueError):
    """Invalid `field_factory` argument."""


class InvalidMetadataTypeError(TypeError):
    """Invalid `metadata_type` argument."""


def make_field_extender[**ParamsT, ReturnT](
    field_factory: Callable[ParamsT, ReturnT],
):
    """

    NOTE: currently handles only one BaseFieldMeta per field!!!
    """

    def wrapped(fi_base: Any, /, *args: ParamsT.args, **kwargs: ParamsT.kwargs) -> ReturnT:
        if not isinstance(fi_base, pydantic_FieldInfo):
            raise TypeError(
                f"Argument 'fi_base' must be of type <pydantic.fields.FieldInfo>, received: {type(fi_base)}"
            )
        fi_extender = field_factory(*args, **kwargs)
        if not isinstance(fi_extender, pydantic_FieldInfo):
            raise InvalidFieldFactoryError(
                "The provided 'field_factory' must be a callable "
                "returning an instance of <pydantic.fields.FieldInfo>, "
                f"got an instance of: {type(fi_extender)}"
            )

        # special merging of custom-field-meta is needed only if
        #   - both FieldInfos have a non-empty 'metadata' attribute (a list)
        #   - both 'metadata' attributes have an item subclassing 'BaseFieldMeta' in them
        #   - both of those items are in fact the same type (i.e. not different subclasses)
        if fi_base.metadata and fi_extender.metadata:
            custom_meta_base: BaseFieldMeta | None = None
            for m in fi_base.metadata:
                if issubclass(type(m), BaseFieldMeta):
                    custom_meta_base = m
                    break
            if custom_meta_base:
                for i, m in enumerate(fi_extender.metadata):
                    if type(m) is type(custom_meta_base):
                        fi_extender.metadata[i] = BaseFieldMeta.extend(custom_meta_base, m)
                        break
        return cast(Any, pydantic_FieldInfo.merge_field_infos(fi_base, fi_extender))

    return wrapped


############################################################
####################  Enchanced Model   ####################


class __EnchancedMetaclass(type(pydantic_BaseModel)):  # type: ignore
    # TODO: is not working from at least pydantic 2.10.6

    # `__getattr__` is in a non-TYPE_CHECKING block because otherwise, mypy allows arbitrary attribute access:
    if not TYPE_CHECKING:  # pragma: no branch

        def __getattr__(self, item: str) -> Any:
            """Get the FieldInfo of a Field, when that Field is accessed from the Model itself."""
            # raises a UserWarning in pydantic._internal._fields.collect_model_fields():
            mf = self.__dict__.get("model_fields")
            if mf and item in mf and not inspect.stack()[1].function == "collect_model_fields":
                return mf[item]
            return super().__getattr__(item)


class EnchancedModelMixin(metaclass=__EnchancedMetaclass):
    pass


############################################################
####################  Fields with Meta  ####################


class BaseFieldMeta(ABC):
    """Upper bound of the `metadata_type` argument of `make_field_with_meta()`."""

    __slots__ = (
        "_explicitly_set_attrs_on_construct",
        "_explicitly_set_attrs_after_construct",
    )

    _explicitly_set_attrs_on_construct: set[str]
    _explicitly_set_attrs_after_construct: set[str]

    @property
    def explicitly_set_attrs(self) -> set[str]:
        """Which attributes were ***explicitly*** set (either on instance creation or after that)."""
        return self._explicitly_set_attrs_on_construct.union(self._explicitly_set_attrs_after_construct)

    @classmethod
    @cache
    def should_add_attrs_from_constructor(cls, *args, **kwargs) -> bool:
        """
        Override (or mokeypatch) to modify if, when and what should be considered as
        an explicitly set attribute when creating the instance like `MyFieldMeta(f_1=v_1, f_2=v_2 ...)`.\n
        NB: Called once for each instance, only on instance creation.

        Default behaviour is caching the result once per child class and is *not* considering the actual args.\n
        Default skips cases when child class' __init__():
        - Is not explicitly defined, i.e. resolves to the default `object.__init__()`
        - Does not have any parameters, i.e. is `def __init__(self): ...`
        """
        init_params = list(inspect.signature(cls.__init__).parameters.values())
        return not (
            cls.__init__.__qualname__ == "object.__init__" or len(init_params) == 0
            # - Accepts only positional varargs, i.e. is `def __init__(self, *args): ...`
            #   This is currently handled by __new__() accepting only **kwargs:
            # or (len(init_params) == 1 and init_params[0] == inspect.Parameter.VAR_POSITIONAL)
        )

    # TODO: maybe allow *args as well?
    #       use cases?
    #       interaction with cls.should_add_attrs_from_constructor()?
    #       interaction with correct dynamic creation from cls._extend()?
    def __new__(cls, /, **kwargs) -> Self:
        """Memorize the explicitly set attributes **when** the instance is being created."""
        instance = super().__new__(cls)
        # TODO: should_add_attrs_from_constructor should be able to filter and return specific keys to add ?
        if cls.should_add_attrs_from_constructor(**kwargs):
            instance._explicitly_set_attrs_on_construct = set(kwargs.keys())
        else:
            instance._explicitly_set_attrs_on_construct = set()
        instance._explicitly_set_attrs_after_construct = set()
        return instance

    @override
    def __setattr__(self, name: str, value: Any) -> None:
        """Memorize the explicitly set attributes **after** the instance is created."""
        caller = inspect.stack()[1].function
        if not (
            caller == "__init__"  # self.__new__() handles the input-args of self.__init__()
            or (
                caller == "__new__"
                and name
                in (
                    "_explicitly_set_attrs_on_construct",
                    "_explicitly_set_attrs_after_construct",
                )
            )
        ):
            self._explicitly_set_attrs_after_construct.add(name)
        super().__setattr__(name, value)

    @classmethod
    def __extend[T: "BaseFieldMeta"](cls, base: T, extender: T) -> T:
        """"""
        all_explicitly_set_attrs = base.explicitly_set_attrs.union(extender.explicitly_set_attrs)
        print()
        print(f"{all_explicitly_set_attrs=}")
        print(f"{base.explicitly_set_attrs=}")
        print(f"{extender.explicitly_set_attrs=}")

        attr_to_val: dict[str, Any] = {}
        for attr in all_explicitly_set_attrs:
            print()
            print(f"{attr=}")
            print(f"{attr in base.explicitly_set_attrs=}")
            print(f"{attr in extender.explicitly_set_attrs=}")
            attr_to_val[attr] = (
                getattr(extender, attr) if attr in extender.explicitly_set_attrs else getattr(base, attr)
            )
        print(f"{attr_to_val=}")
        print()
        return type(base)(**attr_to_val)
        return cls(**attr_to_val)

    @classmethod
    def extend[T: "BaseFieldMeta"](cls, field_meta: T, *field_metas: T) -> T:
        """
        Merge `FieldMeta` instances keeping only explicitly set attributes.\n
        Later `FieldMeta` instances override earlier ones.

        :return: A new `FieldMeta` instance
        """
        on_construct_attr_to_val: dict[str, Any] = {}
        after_construct_attr_to_val: dict[str, Any] = {}
        for m in (field_meta, *field_metas):
            for attr in m._explicitly_set_attrs_on_construct:
                on_construct_attr_to_val[attr] = getattr(m, attr)
            for attr in m._explicitly_set_attrs_after_construct:
                after_construct_attr_to_val[attr] = getattr(m, attr)
        # res = cls(**attr_to_val)
        res = type(field_meta)(**on_construct_attr_to_val)
        for attr, val in after_construct_attr_to_val.items():
            setattr(res, attr, val)
        return res


class __FieldsWithMetaMixin[T](ABC):
    """Provides a correctly typed `fields_meta()` classmethod."""

    @classmethod
    @cache
    @final
    def fields_meta(cls) -> dict[str, T]:
        """A map of the names of all the model fields containing custom metadata to their respective metadata."""
        if not issubclass(cls, pydantic_BaseModel):
            return {}
        res = {}
        for f_name, f_info in cls.model_fields.items():
            for m in f_info.metadata:
                if isinstance(m, BaseFieldMeta):
                    res[f_name] = m
                    break
        return res


def make_field_with_meta[**ParamsT, ReturnT, MetaT: BaseFieldMeta](
    field_factory: Callable[ParamsT, ReturnT],
    metadata_type: type[MetaT],
    *metadata_types: type[MetaT],
):
    """
    Convert the `field-factory` to a new callable with same signature and return type,
    but also allowing for the easy addition of custom metadata.

    :returns:
        Tuple of two elements:\n
        - the provided `field_factory`, but also accepting a new positional-only parameter on first position,
          that must be an instance of the provided `metadata_type` or `None`, and has a default value of `None`
        - TODO
    :raise InvalidFieldFactoryError:
        if the `field_factory` is not returning an instance of `pydantic.fields.FieldInfo`
    :raise InvalidMetadataTypeError:
        if the `metadata_type` is not a subclass of `BaseFieldMeta`
    """

    def wrapper[**InternalParamsT](
        field_factory: Callable[InternalParamsT, ReturnT],
        metadata_type: type[MetaT],
    ):
        def wrapped(
            metadata: MetaT | None = None, /, *args: InternalParamsT.args, **kwargs: InternalParamsT.kwargs
        ) -> ReturnT:
            f = field_factory(*args, **kwargs)
            if not isinstance(f, pydantic_FieldInfo):
                raise InvalidFieldFactoryError(
                    "The provided 'field_factory' must be a callable "
                    "returning an instance of 'pydantic.fields.FieldInfo', "
                    f"got an instance of: <{type(f)}>"
                )
            if metadata is not None:
                if not isinstance(metadata, metadata_type):
                    raise InvalidMetadataTypeError(
                        f"Argument 'metadata' must be an instance of <{metadata_type}>, "
                        f"received instance of: {type(metadata)}"
                    )
                # FieldInfo.metadata differentiates its items by their type, not by their value,
                # so if one item of type dict would be allowed anyway, better to just have one item of type 'metadata_type':
                f.metadata.append(metadata)
            return cast(ReturnT, f)

        return wrapped

    all_metadata_types = [metadata_type, *metadata_types]
    all_metadata_types.reverse()
    if not issubclass(all_metadata_types[0], BaseFieldMeta):
        raise InvalidMetadataTypeError(
            f"Argument 'metadata_type' must be a subclass of {BaseFieldMeta}, received type: {all_metadata_types[0]}"
        )
    res = wrapper(field_factory, all_metadata_types[0])
    # for arg_type in all_metadata_types[1:]:
    #     if not issubclass(arg_type, BaseFieldMeta):
    #         raise InvalidMetadataTypeError(
    #             f"Argument 'metadata_type' must be a subclass of {BaseFieldMeta}, "
    #             f"received type: {arg_type}"
    #         )
    #     res = wrapper(res, arg_type)  # type: ignore
    # return res # TODO: __FieldsWithMetaMixin with all of the metas?
    return res, cast(type[__FieldsWithMetaMixin[MetaT]], __FieldsWithMetaMixin[type(metadata_type)])
