from httpx_oauth.clients import discord, facebook, github, google, linkedin, microsoft, reddit
from httpx_oauth.oauth2 import BaseOAuth2

from config import AppConfig
from config.auth import OAuth2Provider


class _ProviderNotImplementedError(NotImplementedError):
    def __init__(self, p):
        super().__init__(f"OAuth2 provider '{p}' is not yet implemented.")


class _DiscordOAuth2Client(discord.DiscordOAuth2):
    """OAuth2 client for Discord."""

    _provider_ref = OAuth2Provider.DISCORD

    def __init__(self):
        config = AppConfig.OAUTH2.config_for(self._provider_ref)
        super().__init__(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
        )
        raise _ProviderNotImplementedError(self._provider_ref)


class _FacebookOAuth2Client(facebook.FacebookOAuth2):
    """OAuth2 client for Facebook."""

    _provider_ref = OAuth2Provider.FACEBOOK

    def __init__(self):
        config = AppConfig.OAUTH2.config_for(self._provider_ref)
        super().__init__(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
        )


class _GitHubOAuth2Client(github.GitHubOAuth2):
    """OAuth2 client for GitHub."""

    _provider_ref = OAuth2Provider.GITHUB

    def __init__(self):
        config = AppConfig.OAUTH2.config_for(self._provider_ref)
        super().__init__(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
        )


class _GoogleOAuth2Client(google.GoogleOAuth2):
    """OAuth2 client for Google."""

    _provider_ref = OAuth2Provider.GOOGLE

    def __init__(self):
        config = AppConfig.OAUTH2.config_for(self._provider_ref)
        super().__init__(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
            # scopes=["https://www.googleapis.com/auth/userinfo.email"],
        )


class _LinkedInOAuth2Client(linkedin.LinkedInOAuth2):
    """OAuth2 client for LinkedIn."""

    _provider_ref = OAuth2Provider.LINKEDIN

    def __init__(self):
        config = AppConfig.OAUTH2.config_for(self._provider_ref)
        super().__init__(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
        )
        raise _ProviderNotImplementedError(self._provider_ref)


class _MicrosoftOAuth2Client(microsoft.MicrosoftGraphOAuth2):
    """OAuth2 client for Microsoft."""

    _provider_ref = OAuth2Provider.MICROSOFT

    def __init__(self):
        config = AppConfig.OAUTH2.config_for(self._provider_ref)
        super().__init__(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
        )
        raise _ProviderNotImplementedError(self._provider_ref)


class _RedditOAuth2Client(reddit.RedditOAuth2):
    """OAuth2 client for Redit."""

    _provider_ref = OAuth2Provider.REDDIT

    def __init__(self):
        config = AppConfig.OAUTH2.config_for(self._provider_ref)
        super().__init__(
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
        )
        raise _ProviderNotImplementedError(self._provider_ref)


_provider_to_client: dict[OAuth2Provider, type[BaseOAuth2]] = {
    _DiscordOAuth2Client._provider_ref: _DiscordOAuth2Client,
    _FacebookOAuth2Client._provider_ref: _FacebookOAuth2Client,
    _GitHubOAuth2Client._provider_ref: _GitHubOAuth2Client,
    _GoogleOAuth2Client._provider_ref: _GoogleOAuth2Client,
    _LinkedInOAuth2Client._provider_ref: _LinkedInOAuth2Client,
    _MicrosoftOAuth2Client._provider_ref: _MicrosoftOAuth2Client,
    _RedditOAuth2Client._provider_ref: _RedditOAuth2Client,
}


oauth2_clients: dict[OAuth2Provider, BaseOAuth2] = {
    provider: _provider_to_client[provider]()  # type: ignore
    for provider in AppConfig.OAUTH2.ENABLED_PROVIDERS
    if provider in _provider_to_client
}
"""Maps enabled `Providers` to their client instances."""
