import inspect
import typing
from collections.abc import Awaitable, Callable

import makefun
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer

from services.sessions import Session, SessionsService
from services.users import AdminUser, BaseUser, NormalUser, UsersService
from utils import exceptions

from .models import JWT
from .schemas import (
    local_admin_token_scheme,
    local_cookie_scheme,
    local_normal_token_scheme,
    oauth2_token_schemas,
)


def _bearer_token_dependency(
    *deps: OAuth2PasswordBearer | OAuth2AuthorizationCodeBearer | None,
) -> Callable[..., str | None]:
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

    return dependency


class AuthResult[T: BaseUser]:
    """
    Provides:
    - `token`: the token used for the authentication
    - `session`: the `Session` identified by that `token`
    - `user`: (optionally) the `User` identified by that `token`
    """

    __slots__ = ("token", "session", "__user")

    def __init__(self, t: JWT, s: Session, u: BaseUser | None = None):
        self.token, self.session, self.__user = t, s, u

    @property
    def user(self) -> T:
        """The `User`, owning `self.session`."""
        return self.__user  # type: ignore


class _AuthService:
    """Service for authenticating different types of `Users` and their `Sessions`."""

    __slots__ = ("__user_class", "admin", "normal")

    def __init__(self, admin: bool | None = None, normal: bool | None = None):
        """Values of `admin` and `normal` determine the kind of `Users` an instanse of **self** can authenticate."""
        if not (admin or normal):
            raise ValueError(f"{self.__class__.__name__} requires setting at least one of 'admin' or 'normal' to True.")
        self.__user_class = BaseUser if admin and normal else AdminUser if admin else NormalUser
        self.admin, self.normal = admin, normal

    async def authenticate(self, token: str, *, session_only=False) -> AuthResult:
        """Authenticate a `User` with an active `Session` identified by `token`.

        :param bool session_only:
            When **True**, the returned `AuthResult` will not contain the actual `User`s info
            AND **no validation** is performed if a valid `User` can be determined!

        :raise InvalidTokenError:
            If either the `Session` or the `User` couldn't be determined from `token`.

        :return AuthResult:
        """
        jwt = JWT.decode(token)
        # if not jwt.validate_provider():
        #     raise exceptions.InvalidTokenError()
        session = await SessionsService.get(jwt.sub, jwt.jti)
        if session is None or not session.is_valid:
            raise exceptions.InvalidTokenError()
        if session_only:
            return AuthResult(jwt, session)
        user = await UsersService.get_unique_by(self.__user_class, id=jwt.sub)
        # TODO: raise something for FORBIDDEN error ?
        if user is None or user.is_deleted:
            raise exceptions.InvalidTokenError()
        return AuthResult(jwt, session, user)

    def __call__(self, *, session_only=False) -> Callable[..., Awaitable[AuthResult]]:
        """Get a dependency callable for use with `fastapi.Depends` in `fastapi routes` that require authentication.

        :param bool session_only:
            When **True**:
                - the authentication process will try validating **only** the received `Session`
                  and will **not** try validating the respective `User`
                - the resulting `AuthResult` instance will have its *.user* == *None*
                - more performant because skipping at least one more DB request for each authentication
                - usefull for routes that need authentication, but don't need access to the actual authenticated `User`

        :raise fastapi.HttpException:
            If either the `Session` or the `User` couldn't be determined.

        :return:
            A callable that returns a new istance of `AuthResult`.
        """
        assert self.admin is not None or self.normal is not None  # ensured in self.__init__()

        async def dependency(
            cookie: str | None = Depends(local_cookie_scheme),
            bearer: str | None = Depends(
                _bearer_token_dependency(
                    local_admin_token_scheme if self.admin else None,
                    local_normal_token_scheme if self.normal else None,
                    *(oauth2_token_schemas() if self.normal else []),
                )
            ),
        ) -> AuthResult:
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
                return await self.authenticate(
                    typing.cast(str, bearer if bearer else cookie),
                    session_only=session_only,
                )
            except exceptions.InvalidTokenError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer,Cookie"},
                )

        return dependency


AuthAnyUserService: typing.Final[_AuthService] = _AuthService(admin=True, normal=True)
"""Service for authenticating both ADMIN and Normal `Users`."""

AuthAdminUserService: typing.Final[_AuthService] = _AuthService(admin=True)
"""Service for authenticating ADMIN `Users`."""

AuthNormalUserService: typing.Final[_AuthService] = _AuthService(normal=True)
"""Service for authenticating Normal `Users`."""
