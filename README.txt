End goal is an easy to configure and use self-hosted service for user authentication (e.g. to be used in a microservices deployment).

Will include ready to use OAuth2 integration with different pre-built providers
(and code should be obvious and straigthforward for devs on how to add more).
    - currently only google; facebook and github produce some weird errors that need to be debugged

Aims for "plugable" architecture for the storage providers
    - separated by users and services
    - different providers with the same interface (i.e. Users on RDBMS or DynamoDB while Sessions on memcached or Redis etc.)
      (again, aim is for the code to be obvious and straigthforward for devs on how to add more, so the repo can be forked and easily extended).

Will provide a basic (but hopefully enough) API for admin-related tasks.
(Future) Will provide gRPC endpoints for access by other services in the mesh
(Future) Will provide Webhooks subscription interface for access by other services in the mesh


USERS:
    - SuperAdmin: same as Admin, but can delete other Admins, Users and their Sessions
    - Admin: as in a "moderator"
    - User: the actual users of the app this service will be part of


run:
        $ docker compose --profile sessions-{$SESSIONS_PROVIDERS} --profile users-{$USERS_PROVIDERS} up
    currently, the only semi-usable (WIP) provider for both objects is RDBMS (only on Postgresql)
