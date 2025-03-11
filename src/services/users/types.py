import typing

from config.auth import OAuth2Provider


USER_LOGIN_PROVIDER = OAuth2Provider | typing.Literal["local"]
"""The auth provider used by a `User` to log-in."""
