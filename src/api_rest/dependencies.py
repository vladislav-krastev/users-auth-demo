import inspect
import typing

import makefun
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPBasicCredentials,
    OAuth2AuthorizationCodeBearer,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestFormStrict,
)

from api_rest.schemas.auth import (
    local_cookie_scheme,
    local_cookie_scheme_basic_creds,
    local_token_admin_scheme,
    local_token_normal_scheme,
    oauth2_token_schemas,
)
from api_rest.schemas.common import PaginationOffsetLmitRequest
from config import AppConfig
from services.auth import AuthAdminUserService, AuthAnyUserService, AuthNormalUserService, UserAuthResult
from services.users import AdminUser, BaseUser, NormalUser
from utils import exceptions


PaginationOffsetLmitDependency = typing.Annotated[PaginationOffsetLmitRequest, Depends()]
"""Provides mandatory `offset` and `limit` query params."""

PasswordRequestSimpleDependency = typing.Annotated[HTTPBasicCredentials, Depends(local_cookie_scheme_basic_creds)]
"""Required `HTTPBasic Auth` credentials for obtaining a new local-auth Cookie."""
PasswordRequestOAuth2Dependency = typing.Annotated[OAuth2PasswordRequestFormStrict, Depends()]
"""Required `OAuth2 Password Auth` credentials for obtaining a new local-auth AccessToken."""


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


ExternalAuthIsEnabledDependency = Depends(lambda: len(AppConfig.OAUTH2.ENABLED_PROVIDERS) > 1)
"""Required provided configuration for at least one external (OAuth2) provider."""


__AuthServiceType = AuthAnyUserService.__class__


def __make_auth_dependency(service: __AuthServiceType, /, *, session_only=False):
    """Create a dependency for HTTP routes that require authentication.

    :param bool session_only:
        When **True**:
        - the authentication flow will try validating **only** the received `Session`
          and will **not** try validating the respective `User`
        - the resulting `AuthResult` instance will have its *.user* == *None*
        - more performant because it'll skip at least one more back-end request for each authentication
        - usefull for routes that need authentication, but don't need access to the actual authenticated `User`

    :raise fastapi.HttpException:
        If either the `Session` or the `User` couldn't be determined.

    :return fastapi.Depends:
        Returning a new istance of `UserAuthResult`.
    """

    def bearer_token_dependency(*deps: OAuth2PasswordBearer | OAuth2AuthorizationCodeBearer | None):
        """Produce correctly-typed input for `fastapi.Depends()` for requiring AccessTokens in a request's headers."""
        parameters: list[inspect.Parameter] = [
            inspect.Parameter(name=f"_{i}", kind=inspect.Parameter.KEYWORD_ONLY, default=Depends(dep))
            for i, dep in enumerate(deps)
            if dep is not None
        ]

        @makefun.with_signature(inspect.Signature(parameters))
        def dependency(**kwargs: str) -> str | None:
            for token in kwargs.values():
                if token is not None:
                    return token

        return Depends(dependency)

    async def dependency(
        cookie: str | None = Depends(local_cookie_scheme),
        bearer: str | None = bearer_token_dependency(
            local_token_admin_scheme if service.for_admin else None,
            local_token_normal_scheme if service.for_normal else None,
            *(oauth2_token_schemas() if service.for_normal else []),
        ),
    ) -> UserAuthResult:
        if bearer and cookie:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many credentials - send either a Bearer Token or a Cookie, but not both",
            )
        if not (bearer or cookie):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing credentials",
                headers={"WWW-Authenticate": "Bearer,Cookie"},
            )
        try:
            return await service.authenticate(
                token=typing.cast(str, bearer if bearer else cookie),
                session_only=session_only,
            )
        except exceptions.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer,Cookie"},
            )

    return Depends(dependency)


AnyAuthDependency = __make_auth_dependency(AuthAnyUserService, session_only=True)
"""Required authentication by either an ADMIN or a normal `User`."""
AnyUserDependency = typing.Annotated[UserAuthResult[BaseUser], __make_auth_dependency(AuthAnyUserService)]
"""The result of a successfully authenticated either an ADMIN or a normal `User`."""


NormalAuthDependency = __make_auth_dependency(AuthNormalUserService, session_only=True)
"""Required authentication by a normal `User`."""
NormalUserDependency = typing.Annotated[UserAuthResult[NormalUser], __make_auth_dependency(AuthNormalUserService)]
"""The result of a successfully authenticated normal `User`."""


AdminAuthDependency = __make_auth_dependency(AuthAdminUserService, session_only=True)
"""Required authentication by an ADMIN `User`."""
AdminUserDependency = typing.Annotated[UserAuthResult[AdminUser], __make_auth_dependency(AuthAdminUserService)]
"""The result of a successfully authenticated ADMIN `User`."""


def __is_super_admin(auth: AdminUserDependency) -> None:
    if not auth.user.is_admin_super:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a super admin.",
        )


AdminSuperAuthDependency = Depends(__is_super_admin)
"""Required authentication by a Super ADMIN `User`."""
