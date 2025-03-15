import typing

from services.sessions import Session, SessionsService
from services.users import AdminUser, BaseUser, NormalUser, UsersService
from utils import exceptions

from .models import JWT


class ClientAuthResult:
    """TODO: authenticationg another (external client) service for accessing the gRPC and/or the Webhooks API."""


class UserAuthResult[T: BaseUser]:
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


class _UserAuthService:
    """Service for authenticating different types of `Users` and their `Sessions`."""

    __slots__ = ("__user_class", "for_admin", "for_normal")

    def __init__(self, *, for_admin: bool = False, for_normal: bool = False):
        """Service for authenticating different types of `Users` and their `Sessions`.

        :param bool admin:
            To authenticate ADMIN `Users` only.
        :param bool normal:
            To authenticate Normal `Users` only.

        If both `admin` and `normal` == **True**, will authenticate both types of `Users`.

        :raise ValueError:
            If both `admin` and `normal` == **False**.
        """
        if not (for_admin or for_normal):
            raise ValueError(f"{self.__class__.__name__} requires setting at least one of 'admin' or 'normal' to True.")
        self.__user_class = BaseUser if for_admin and for_normal else AdminUser if for_admin else NormalUser
        self.for_admin, self.for_normal = for_admin, for_normal

    async def authenticate(self, token: str, *, session_only=False) -> UserAuthResult:
        """Authenticate a `User` with an active `Session` identified by `token`.

        :param bool session_only:
            When **True**, the returned `AuthResult` will not contain the actual `User`s info
            AND **no validation** is performed if a valid `User` can be determined!

        :raise InvalidTokenError:
            If either the `Session` or the `User` couldn't be determined from `token`.

        :return UserAuthResult:
        """
        jwt = JWT.decode(token)
        session = await SessionsService.get(jwt.sub, jwt.jti)
        if session is None or not session.is_valid:
            raise exceptions.InvalidTokenError("No valid session found for provided token")
        if session_only:
            return UserAuthResult(jwt, session)
        user = await UsersService.get_unique_by(self.__user_class, id=jwt.sub)
        # TODO: raise something for FORBIDDEN error ?
        if user is None or user.is_deleted:
            raise exceptions.InvalidTokenError("No valid user found for provided token")
        return UserAuthResult(jwt, session, user)


AuthAnyUserService: typing.Final[_UserAuthService] = _UserAuthService(for_admin=True, for_normal=True)
"""Service for authenticating both ADMIN and Normal `Users`."""

AuthAdminUserService: typing.Final[_UserAuthService] = _UserAuthService(for_admin=True)
"""Service for authenticating ADMIN `Users`."""

AuthNormalUserService: typing.Final[_UserAuthService] = _UserAuthService(for_normal=True)
"""Service for authenticating Normal `Users`."""
