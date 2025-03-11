import pydantic

from config.auth import OAuth2Provider


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
