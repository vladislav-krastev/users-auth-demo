import asyncio
from enum import StrEnum

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from httpx_oauth.integrations.fastapi import OAuth2AuthorizeCallback
from httpx_oauth.oauth2 import BaseOAuth2, OAuth2Token

from api_rest.dependencies import (
    AnyUserDependency,
    ExternalAuthIsEnabledDependency,
    PasswordRequestOAuth2Dependency,
    PasswordRequestSimpleDependency,
    raise_if_local_auth_disabled,
)
from api_rest.exceptions import SERVICE_UNAVAILABLE_EXCEPTION
from api_rest.schemas.auth import OAuth2AuthorizationUrlResponse, SwaggerUIOAuth2TokenRequest
from api_rest.schemas.common import HTTPExceptionResponse, Item
from api_rest.schemas.user import UserRegisterRequest, UserRegisterResponse
from config import AppConfig
from config.auth import OAuth2Provider
from services.auth.models import JWT, AccessToken
from services.auth.providers import oauth2_clients
from services.sessions import Session, SessionsService
from services.users import BaseUser, NormalUser, UsersService
from utils import password


_PATH_AUTH = "/auth"
_TAG_AUTH = "Authentication"
_TAG_AUTH_LOCAL = "Authentication - Local"
_TAG_AUTH_EXTERNAL = "Authentication - External"


router_auth = APIRouter()


####################
#   Local
####################

__router_auth_local = APIRouter(
    responses={
        status.HTTP_403_FORBIDDEN: {"model": HTTPExceptionResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
)


@__router_auth_local.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=Item[UserRegisterResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": HTTPExceptionResponse},
    },
)
async def register(
    body: UserRegisterRequest,
) -> Item[NormalUser]:
    """Register a new `User`."""
    raise_if_local_auth_disabled()
    if await UsersService.get_unique_by(is_deleted=None, email=body.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The email '{body.email}' is already taken.",
        )
    user = await UsersService.create(NormalUser(email=body.email, password=password.hash_create(body.password)))
    if user is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    return {"data": user}


@__router_auth_local.post(
    "/login",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": HTTPExceptionResponse},
    },
)
async def get_cookie(
    form_data: PasswordRequestSimpleDependency,
    query_as_admin: bool = Query(False, alias="as_admin"),
    *,
    response: Response,
) -> None:
    """ """
    if not query_as_admin:
        raise_if_local_auth_disabled(for_cookie=True)
    user: BaseUser | None = (
        await UsersService.get_unique_by(username=form_data.username)
        if query_as_admin
        else await UsersService.get_unique_by(email=form_data.username)
    )
    if user is None or user.password is None or not password.hash_verify(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Cookie"},
        )
    jwt = JWT.create_for_user(user, AppConfig.LOCAL_AUTH.COOKIE.EXPIRE_MINUTES, "local")
    if not await SessionsService.create(Session.from_jwt(jwt, type="cookie")):
        raise SERVICE_UNAVAILABLE_EXCEPTION
    response.set_cookie(
        key=AppConfig.LOCAL_AUTH.COOKIE.NAME,
        value=jwt.encode(),
        max_age=AppConfig.LOCAL_AUTH.COOKIE.EXPIRE_MINUTES * 60,
        secure=True,
        httponly=True,
        samesite="lax",
    )


@__router_auth_local.post(
    "/login/access-token",
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
    responses={
        # status.HTTP_201_CREATED: {"headers": {"Cache-Control": "no-store"}},  # TODO: not showing in SwaggerUI docs
        status.HTTP_401_UNAUTHORIZED: {"model": HTTPExceptionResponse},
    },
)
async def get_token(
    form_data: PasswordRequestOAuth2Dependency,
    query_as_admin: bool = Query(False, alias="as_admin"),
    *,
    response: Response,
) -> AccessToken:
    """ """
    if not query_as_admin:
        raise_if_local_auth_disabled(for_token=True)
    user: BaseUser | None = (
        await UsersService.get_unique_by(username=form_data.username)
        if query_as_admin
        else await UsersService.get_unique_by(email=form_data.username)
    )
    if user is None or user.password is None or not password.hash_verify(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    jwt = JWT.create_for_user(user, AppConfig.LOCAL_AUTH.ACCESS_TOKEN.EXPIRE_MINUTES, "local")
    if not await SessionsService.create(Session.from_jwt(jwt, type="token")):
        raise SERVICE_UNAVAILABLE_EXCEPTION
    response.headers["Cache-Control"] = "no-store"
    return AccessToken(access_token=jwt.encode())


####################
#   External OAuth2
####################

__router_auth_external = APIRouter(
    dependencies=[ExternalAuthIsEnabledDependency],
)


def _validate_oauth2_provider_name(provider: OAuth2Provider) -> None:
    """Check if the `provider` is enabled.

    :raise HTTP_400_BAD_REQUEST:
        If the `provider` is not enabled.
    """
    if provider not in AppConfig.OAUTH2.ENABLED_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider not enabled - allowed values are: {AppConfig.OAUTH2.ENABLED_PROVIDERS}",
        )


async def _jwt_from_oauth2_access_token(provider: OAuth2Provider, client: BaseOAuth2, token: OAuth2Token) -> JWT | None:
    """Produce a `JWT` from a `Provider's` AccessToken, so it can be used to create an internal AccessToken.

    :return JWT:
        If it was created.
    :return None:
        If it couldn't be created.
    """
    email = (await client.get_id_email(token["access_token"]))[1]
    if email is None:
        return None

    user = await UsersService.get_unique_by(email=email)
    if not user:
        user = await UsersService.create(NormalUser(email=email, password=None))
        if not user:
            return None

    jwt = JWT.create_for_user(user, AppConfig.OAUTH2.config_for(provider).ACCESS_TOKEN_EXPIRE_MINUTES, provider)
    if not await SessionsService.create(Session.from_jwt(jwt, type="token")):
        return None
    return jwt


OAuth2ProviderEnabled = StrEnum(
    "OAuth2ProviderEnabled", [(p.name, p.value) for p in OAuth2Provider if p in AppConfig.OAUTH2.ENABLED_PROVIDERS]
)


@__router_auth_external.get(
    "/oauth2-authorization-url/{provider}",
    name="OAuth2 Provider URL",
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": HTTPExceptionResponse},
    },
)
async def oauth2_authorize(
    # TODO: this makes the OpenAPI schema obsolete when a new provider is enabled (including just from the config),
    #       maybe type-hint with 'OAuth2Provider' and return an HTTP exception when a non-enabled provider is used:
    provider: OAuth2ProviderEnabled,  # type: ignore
    *,
    request: Request,
) -> OAuth2AuthorizationUrlResponse:
    """Get the authorization URL for the specified OAuth2 `provider`."""
    _validate_oauth2_provider_name(provider)
    oauth2_client = oauth2_clients[provider]
    return OAuth2AuthorizationUrlResponse(
        authorization_url=(
            await oauth2_client.get_authorization_url(
                redirect_uri=str(request.url_for(AppConfig.OAUTH2.REDIRECT_ROUTE_NAME)),
                state=provider,
            )
        )
    )


# https://www.facebook.com/v5.0/dialog/oauth?response_type=code&client_id=1147333743597470&redirect_uri=http%3A%2F%2Flocalhost%3A8080%2Fauth%2Foauth2-redirect%2F&state=facebook&scope=email+public_profile


# code=AQAFcNbhPe7XN8t_MXERnoodfvlsUZSoGnHmWe3kDuJk1Vm1hydEvr4F3a6m3_6h9JTNTNeYN94WWT_iSHaQBRqh_ESAexw5bRWsOtf0tmKWO-ZZNuR9GMGHjVtHci6HaJAV5Y08FoAXC55nsfwvj_hVWofsV_rSKK_4VbMPwje3vFhY08zKZHLlQ75hd3iEm3X4ddbLIyExs3IFo-6BkrF0RgaA8LJvB5nB0mdSd38pcgpUg24sR3m4VU__TtugvunuFQDaakKOg5nOAi_BTtxkb2yGIV9YNAyfOLfAYrkF1-nZv9D_w1kFZLjwXVkFHpqbPJf5g1LUlFBig9gUQryBPozKGXBGFzf4xBNQgccmEfV89MHrrOJ6zsyt-piNycc
# state=facebook
@__router_auth_external.get(
    AppConfig.OAUTH2.REDIRECT_ROUTE_PATH,
    name=AppConfig.OAUTH2.REDIRECT_ROUTE_NAME,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
)
async def oauth2_redirect(
    query_code: str | None = Query(default=None, alias="code"),
    query_code_verifier: str | None = Query(default=None, alias="code_verifier"),
    query_state: str | None = Query(default=None, alias="state"),
    query_error: str | None = Query(default=None, alias="error"),
    *,
    request: Request,
    response: Response,
) -> AccessToken:
    """ """
    # REMINDER: SwaggerUI currently supports only a single redirect_url for all OAuth2 flows,
    # so instead of having a dedicated local URL per provider
    # (e.g. '/auth/oauth2-redirect/github', '/auth/oauth2-redirect/google' etc),
    # the correct provider is saved, transmited and deduced using the 'state'.

    invalid_query_state = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Received invalid query param: state",
    )
    if query_state is None and query_error is None:
        raise invalid_query_state
    provider: OAuth2Provider | None = None
    for v in OAuth2Provider.__members__.values():  # no need for the fancier OAuth2Provider(query_state)
        if query_state == v.value:
            provider = v
    if provider is None:
        raise invalid_query_state
    _validate_oauth2_provider_name(provider)
    oauth2_client = oauth2_clients[provider]
    callback_handler = OAuth2AuthorizeCallback(
        oauth2_client,
        redirect_url=str(request.url_for(AppConfig.OAUTH2.REDIRECT_ROUTE_NAME)),
    )
    oauth2_token = (
        await callback_handler(  # TODO: facebook client fails on .get_access_token()
            request,
            query_code,
            query_code_verifier,
            query_state,
            query_error,
        )
    )[0]
    jwt = await _jwt_from_oauth2_access_token(provider, oauth2_client, oauth2_token)
    if jwt is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    response.headers["Cache-Control"] = "no-store"
    return AccessToken(access_token=jwt.encode())


####################
#   SwaggerUI OAuth2
####################


__router_auth_external_swaggerui = APIRouter()


async def _parse_swaggerui_token_request(request: Request) -> SwaggerUIOAuth2TokenRequest:
    """Parse and try to verify the SwaggerUI get-oauth2-access-token request.

    :raise HTTP_400_BAD_REQUEST:
        When any of the following is true:\n
        - any of the query params is missing
        - the values of `grant_type` and `redirect_uri` are incorrect
        - a valid `provider` could not be deduced from `client_id` and `client_secret`

    :raise HTTP_403_FORBIDDEN:
        When the `referer` request header is missing or has an incorrect value
    """
    # TODO: what other things should be verified?

    # TODO: obviously the 'referer' header should also allow other values:
    if "referer" not in request.headers or request.headers["referer"] != f"{AppConfig.HOST_URL}/docs":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)  # no exception details, just in case

    body = QueryParams(await request.body())
    bad_request = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Received invalid query param: {param}",
    )

    if "grant_type" not in body or body["grant_type"] != "authorization_code":
        bad_request.detail = bad_request.detail.format(param="grant_type")
        raise bad_request
    if "redirect_uri" not in body or body["redirect_uri"] != str(request.url_for(AppConfig.OAUTH2.REDIRECT_ROUTE_NAME)):
        bad_request.detail = bad_request.detail.format(param="redirect_uri")
        raise bad_request
    for param in ("code", "client_id", "client_secret"):
        if param not in body:
            bad_request.detail = bad_request.detail.format(param=param)
            raise bad_request

    provider: OAuth2Provider | None = None
    for p in AppConfig.OAUTH2.ENABLED_PROVIDERS:
        config = AppConfig.OAUTH2.config_for(p)
        if body["client_id"] == config.CLIENT_ID and body["client_secret"] == config.CLIENT_SECRET:
            provider = p
            break
    if provider is None:
        bad_request.detail = bad_request.detail.format(param="client_id and/or client_secret")
        raise bad_request

    return SwaggerUIOAuth2TokenRequest(
        provider=provider,
        grant_type=body["grant_type"],
        code=body["code"],
        client_id=body["client_id"],
        client_secret=body["client_secret"],
        redirect_uri=body["redirect_uri"],
    )


from typing import Annotated

from fastapi import Depends
from fastapi.datastructures import QueryParams


@__router_auth_external_swaggerui.post(
    AppConfig.OAUTH2.SWAGGERUI_TOKEN_PATH,
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
    include_in_schema=False,
)
async def oauth2_swaggerui_token(
    body: Annotated[SwaggerUIOAuth2TokenRequest, Depends(_parse_swaggerui_token_request)],
    *,
    request: Request,
    response: Response,
) -> AccessToken:
    """Produce a valid AccessToken for logging-in with the OAuth2-AuthCode SwaggerUI forms.

    Reminder on why this is needed:
    Having the SwaggerUI OAuth2-AuthorizationCode forms call the real tokenURL for a given provider
    will later result in SwaggerUI sending us the provider's actual AccessToken, that:
    - we'll know nothing about, as the flow never called our `/oauth2_redirect` *path*
    - cannot use, as we operate only internal AccessTokens (generated from the providers' AccessTokens)
    """
    oauth2_client = oauth2_clients[body.provider]
    callback_handler = OAuth2AuthorizeCallback(oauth2_client, redirect_url=body.redirect_uri)
    try:
        oauth2_token = (await callback_handler(request, body.code))[
            0
        ]  # TODO: facebook client fails on .get_access_token()
        print(f"{oauth2_token=}")
    except Exception as err:
        print(err)
    jwt = await _jwt_from_oauth2_access_token(body.provider, oauth2_client, oauth2_token)
    if jwt is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    response.headers["Cache-Control"] = "no-store"
    return AccessToken(access_token=jwt.encode())


####################
#   Common
####################


@router_auth.post(
    "/logout",
    tags=[_TAG_AUTH],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": HTTPExceptionResponse}},
)
async def logout(
    *,
    auth: AnyUserDependency,
) -> None:
    """Logout a `User`.

    No difference if the corresponding `Session` is already invalid.
    """
    # TODO: the AuthService should propagate the auth bearer (cookie or token),
    #       so this method can invalidate the Cookie (set expiration date in the past)

    # don't check response, as user should be able to alwais logout, even if session invalidation failed:
    asyncio.create_task(SessionsService.invalidate(auth.token.sub, auth.token.jti))


router_auth.include_router(__router_auth_local, prefix=_PATH_AUTH, tags=[_TAG_AUTH_LOCAL])
router_auth.include_router(__router_auth_external, prefix=_PATH_AUTH, tags=[_TAG_AUTH_EXTERNAL])
router_auth.include_router(__router_auth_external_swaggerui, prefix=_PATH_AUTH)
