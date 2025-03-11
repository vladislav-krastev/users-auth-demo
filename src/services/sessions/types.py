import typing

from config.auth import OAuth2Provider


SESSION_PROVIDER = OAuth2Provider | typing.Literal["local"]
"""The auth provider a `Session` represents."""

SESSION_TYPE = typing.Literal["cookie", "token"]
"""What kind of auth bearer a given `Session` represents."""
