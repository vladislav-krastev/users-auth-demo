from functools import lru_cache

import pydantic
from fastapi.security import APIKeyCookie, HTTPBasic, OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer

from config import AppConfig
from config.auth import OAuth2Provider
from services.auth.providers import oauth2_clients
from utils import exceptions


class OAuth2AuthorizationUrlResponse(pydantic.BaseModel):
    """Response body for the correct AuthURL for authenticating a `User` with a given OAuth2 `provider`."""

    authorization_url: str


class SwaggerUIOAuth2TokenRequest(pydantic.BaseModel):
    """Request body for creating a new OAuth2 Authorization Token.

    Helps providing the SwaggerUI OAuth2 forms for external `providers` with our own Access Tokens
    instead of the actual Access Tokens returned from the actual OAuth2 `provider`.

    **ONLY** internally used!!!
    """

    provider: OAuth2Provider
    grant_type: str
    code: str
    client_id: str
    client_secret: str
    redirect_uri: str


local_cookie_scheme_basic_creds = HTTPBasic(
    scheme_name="Cookie credentials",
    description="Auto-sent when hitting the '/auth/login' URL to obtain a new Cookie",
)

local_cookie_scheme = APIKeyCookie(
    name=AppConfig.LOCAL_AUTH.COOKIE.NAME,
    scheme_name="Cookie",
    description="Obtained from hitting the 'auth/login' URL",
    auto_error=False,
)

local_token_admin_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login/access-token?as_admin=true",  # TODO: more dynamic way of auto-setting the URL?
    scheme_name="Admin - Token Local",
    auto_error=False,
)

local_token_normal_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login/access-token",  # TODO: more dynamic way of auto-setting the URL?
    scheme_name="User - Token Local",
    auto_error=False,
)


@lru_cache(maxsize=1)
def oauth2_token_schemas() -> list[OAuth2AuthorizationCodeBearer]:
    """Produce a list of `Authorization: Bearer` schemas - an item for each of the ENABLED Oauth2 `Providers`."""
    deps = []
    for provider in AppConfig.OAUTH2.ENABLED_PROVIDERS:
        client = oauth2_clients[provider]
        if not client.base_scopes:
            raise exceptions.InvalidOauth2ConfigError(provider=provider, message="'base_scopes' is missing")
        deps.append(
            OAuth2AuthorizationCodeBearer(
                authorizationUrl=client.authorize_endpoint,
                # see the docs of '/auth{AppConfig.OAUTH2.SWAGGERUI_TOKEN_PATH}' endpoint on why this is needed:
                tokenUrl=f"{AppConfig.HOST_URL}/auth{AppConfig.OAUTH2.SWAGGERUI_TOKEN_PATH}",
                refreshUrl=None,  # TODO
                scopes={s: "" for s in client.base_scopes},
                scheme_name=f"{provider.capitalize()}",
                description=None,
                auto_error=False,
            )
        )
    return deps
