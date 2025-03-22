import typing

from config.auth import OAuth2Provider
from services.events.events import EVENT


####################
#   Auth
####################


class AuthConfigError(ValueError):
    """Base exception for any errors related to bad configurations of the `AuthService"."""


class InvalidOauth2ConfigError(AuthConfigError):
    """The config for a used Oauth2 `Provider` is wrong or missing."""

    def __init__(self, provider: OAuth2Provider, message):
        """The config for a used Oauth2 `Provider` is wrong or missing."""
        super().__init__(f"Wrong or missing config for Oauth2 provider '{provider}': {message}")


class AuthError(ValueError):
    """ """


class InvalidTokenError(AuthError):
    """ """


class InvalidJWTError(InvalidTokenError):
    """ """


class InvalidSessionError(AuthError):
    """ """


####################
#   Events
####################


class EventError(ValueError):
    """Base exception for any errors related to internal `Events`."""


class InvalidEventError(EventError):
    """An event-handler doesn't know how to handle a received `Event`."""

    def __init__(self, handler_name: str, event: EVENT):
        """An event-handler doesn't know how to handle a received `Event`."""
        super().__init__(f"Event-handler '{handler_name}' cannot process event '{event.name}'")


####################
#   Select Filters
####################


class FilterError(ValueError):
    """Base exception for any errors related to filtering objects from a storage `Provider`."""

    def __init__(self, message: str | None = None):
        """Base exception for any errors related to filtering objects from a storage `Provider`."""
        super().__init__(message if message is not None else "An error occured while processing a filter.")


class FilterMissingError(FilterError):
    """A filter is required, but was not provided."""

    def __init__(self):
        """A filter is required, but was not provided."""
        super().__init__("A filter is required, but was not provided.")


class FilterNotAllowedError(FilterError, TypeError):
    """The provided key or value of the provided filter is not allowed."""

    def __init__(self, k: str, v: typing.Any):
        """The provided key or value of the provided filter is not allowed."""
        super().__init__(f"The provided filter with key: '{k}' of type: '{type(v)}' and value: '{v}' is not allowed.")


class FilterNotUniqueError(FilterError):
    """The combination of the provided one or more filters didn't produce a unique object."""

    def __init__(self, class_: type, clause: typing.Literal["AND", "OR"], **filters: typing.Any):
        """The combination of the provided one or more filters didn't produce a unique object."""
        super().__init__(
            f"The provided filters {filters}, combined with '{clause}', resolved to multiple instances of {class_}."
        )
