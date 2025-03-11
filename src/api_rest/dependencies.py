import typing

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPBasicCredentials,
    OAuth2PasswordRequestFormStrict,
)

from api_rest.schemas.common import PaginationOffsetLmitRequest
from config import AppConfig
from services.auth import AuthAdminUserService, AuthAnyUserService, AuthNormalUserService, AuthResult
from services.auth.schemas import local_cookie_scheme_basic_creds
from services.users import AdminUser, BaseUser, NormalUser


PaginationOffsetLmitDependency = typing.Annotated[PaginationOffsetLmitRequest, Depends()]
"""Provides mandatory `offset` and `limit` query params."""

PasswordRequestSimpleDependency = typing.Annotated[HTTPBasicCredentials, Depends(local_cookie_scheme_basic_creds)]
"""Required `HTTPBasic Auth` credentials for obtaining a new local-auth Cookie."""
PasswordRequestOAuth2Dependency = typing.Annotated[OAuth2PasswordRequestFormStrict, Depends()]
"""Required `OAuth2 Password Auth` credentials for obtaining a new local-auth AccessToken."""

AnyAuthDependency = Depends(AuthAnyUserService(session_only=True))
"""Required authentication by either an ADMIN or a normal `User`."""
AnyUserDependency = typing.Annotated[AuthResult[BaseUser], Depends(AuthAnyUserService())]
"""The result of a successfully authenticated either an ADMIN or a normal `User`."""


AdminAuthDependency = Depends(AuthAdminUserService(session_only=True))
"""Required authentication by an ADMIN `User`."""
AdminUserDependency = typing.Annotated[AuthResult[AdminUser], Depends(AuthAdminUserService())]
"""The result of a successfully authenticated ADMIN `User`."""


def __is_super_admin(auth: AdminUserDependency):
    if not auth.user.is_admin_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a super admin.",
        )


AdminSuperAuthDependency = Depends(__is_super_admin)
"""Required authentication by a Super ADMIN `User`."""


NormalAuthDependency = Depends(AuthNormalUserService(session_only=True))
"""Required authentication by a normal `User`."""
NormalUserDependency = typing.Annotated[AuthResult[NormalUser], Depends(AuthNormalUserService())]
"""The result of a successfully authenticated normal `User`."""


def raise_if_local_auth_disabled(for_cookie: bool = False, for_token: bool = False) -> None:
    """Checks if local authentication (+ optionally with a Cookie or an AccessToken) is disabled.

    :raise ValueError:
        When trying to check both `for_cookie` and `for_token`.

    :raise HTTP_403_FORBIDDEN:
        When local auth is disabled or is enabled in general,
        but is disabled for auth with a Cookie or an AccessToken (if `for_cookie` or `for_token` was provided).
    """
    if for_cookie and for_token:
        raise ValueError("Can't depend both on a 'cookie' and on a 'token'")
    msg = [
        "Registering a local user",
        "Local authentication with a Cookie",
        "Local authentication with an AccessToken",
    ]
    extended_check = (
        AppConfig.LOCAL_AUTH.COOKIE_ENABLED is True
        if for_cookie
        else AppConfig.LOCAL_AUTH.ACCESS_TOKEN_ENABLED is True
        if for_token
        else True
    )
    if not AppConfig.LOCAL_AUTH.IS_ENABLED and not extended_check:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{msg[for_cookie + 2 * for_token]} is not allowed.",
        )


ExternalAuthEnabledDependency = Depends(lambda: len(AppConfig.OAUTH2.ENABLED_PROVIDERS) > 1)
"""Required provided configuration for at least one external (OAuth2) provider."""
