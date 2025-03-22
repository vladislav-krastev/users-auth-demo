import asyncio
import typing
from functools import partial

from fastapi import APIRouter, HTTPException, Query, Request, status

from api_rest.dependencies import (
    AdminAuthDependency,
    AdminSuperAuthDependency,
    AdminUserDependency,
    PaginationOffsetLmitDependency,
)
from api_rest.exceptions import SERVICE_UNAVAILABLE_EXCEPTION
from api_rest.schemas.admin import (
    AdminCreateRequest,
    AdminGetSessionResponse,
    AdminGetUserResponse,
    AdminResponse,
)
from api_rest.schemas.common import (
    HTTPExceptionResponse,
    Item,
    ItemPaginated,
)
from config.app import AppConfig, _AppConfig
from services.sessions import Session, SessionsService
from services.users import AdminUser, NormalUser, UsersService
from utils import pagination, password


_PATH_ADMIN = "/admins"
_PATH_USER = "/users"
_TAG_ADMIN = "Admin"
_TAG_ADMIN_SUPER = "Super Admin"


router_admins = APIRouter()


####################
#   Super Admin
####################


@router_admins.get(
    "/config",
    tags=[_TAG_ADMIN_SUPER],
    status_code=status.HTTP_200_OK,
    responses={
        # **admin_auth_exceptions,
        status.HTTP_403_FORBIDDEN: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminSuperAuthDependency],
)
async def get_current_config() -> Item[_AppConfig]:
    """Get the currently applied configurations."""
    return {"data": AppConfig}


__router_admins_super = APIRouter(
    responses={
        # **admin_auth_exceptions,
        status.HTTP_403_FORBIDDEN: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminSuperAuthDependency],
)


@__router_admins_super.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=Item[AdminResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": HTTPExceptionResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
)
async def create_new_admin(
    body: AdminCreateRequest,
) -> Item[AdminUser]:
    """Create a new ADMIN `User`."""
    if await UsersService.get_unique_by(username=body.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A user with username '{body.username}' already exists.",
        )
    admin = await UsersService.create(AdminUser(username=body.username, password=password.hash_create(body.password)))
    if not admin:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    return {"data": admin}


@__router_admins_super.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_admin_or_user(
    user_id: str,
) -> None:
    """Delete an ADMIN or a normal `User`."""
    # a user should always be deletable, even if session invalidation or user-deletion failed:
    asyncio.gather(
        SessionsService.invalidate_all(user_id),
        UsersService.delete(user_id),
        return_exceptions=True,
    )


@__router_admins_super.delete(
    "/{user_id}/sessions/",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
)
async def invalidate_sessions_all(
    user_id: str,
) -> None:
    """Invalidate all `Sessions` of the `User` with ID `user_id`."""
    if not await SessionsService.invalidate_all(user_id):
        raise SERVICE_UNAVAILABLE_EXCEPTION


@__router_admins_super.delete(
    "/{user_id}/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
)
async def invalidate_sessions_single(
    user_id: str,
    session_id: str,
) -> None:
    """Invalidate the `Session` with ID `session_id` of the `User` with ID `user_id`."""
    if not await SessionsService.invalidate(user_id, session_id):
        raise SERVICE_UNAVAILABLE_EXCEPTION


# @__router_admins_normal.get(
#     "/logins/",
#     status_code=status.HTTP_200_OK,
#     response_model=ItemPaginated[AdminGetSessionResponse],
#     dependencies=[AdminAuthDependency],
# )
async def get_logins():
    pass


####################
#   Normal Admin
####################


__router_admins_normal = APIRouter(
    responses={
        # **admin_auth_exceptions,
        # status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
)


@__router_admins_normal.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=ItemPaginated[AdminResponse],
    responses={
        # **admin_auth_exceptions,
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminAuthDependency],
)
async def get_admins_all(
    query_pagination: PaginationOffsetLmitDependency,
    query_only_active: bool = Query(False, alias="only_active"),
    *,
    req: Request,
) -> ItemPaginated[AdminUser]:
    """
    Get all or only the currently logged-in ADMIN `Users`.

    When `only_active` == **TRUE**, values for the `offset` query param become opaque:\n
    - always start with `offset` == 0
    - only use the value for offset in the `next` key in the response for `offsets` for subsequent pages,
    otherwise some records might (probably will) be duplicated accross pages and/or skipped entirely
    """
    if query_only_active:
        users, explicit_offset = await pagination.get_in_memory_filtered(
            query_pagination.offset,
            query_pagination.limit,
            getter=partial(UsersService.get_many, AdminUser, limit=query_pagination.limit),
            filter=SessionsService.filter_out_inactive,
        )
    else:
        users = await UsersService.get_many(AdminUser, offset=query_pagination.offset, limit=query_pagination.limit)
        explicit_offset = None
    if users is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    return {
        "count": len(users),
        "next": pagination.http_offset_limit_next_link(
            req,
            len(users),
            explicit_offset,
        ),
        "data": users,
    }


@__router_admins_normal.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=Item[AdminResponse],
)
async def get_me(*, auth: AdminUserDependency) -> Item[AdminUser]:
    """Get current ADMIN."""
    return {"data": auth.user}


@__router_admins_normal.get(
    "/{username}",
    status_code=status.HTTP_200_OK,
    response_model=Item[AdminResponse],
    responses={status.HTTP_404_NOT_FOUND: {"model": HTTPExceptionResponse}},
    dependencies=[AdminAuthDependency],
)
async def get_admin(
    username: str,
) -> Item[AdminUser]:
    """Get the ADMIN `User` with the specified `username`."""
    admin = await UsersService.get_unique_by(AdminUser, username=username)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"An ADMIN with username '{username}' does not exist.",
        )
    return {"data": admin}


####################
#   Users
####################


__router_users = APIRouter(
    responses={
        # **admin_auth_exceptions,
        # status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
)


@__router_users.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=ItemPaginated[AdminGetUserResponse],
    responses={
        # **admin_auth_exceptions,
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminAuthDependency],
)
async def get_users_all(
    query_pagination: PaginationOffsetLmitDependency,
    query_only_active: bool = Query(False, alias="only_active"),
    *,
    req: Request,
) -> ItemPaginated[NormalUser]:
    """Get all or only the currently logged-in normal `Users`.

    When `only_active` == **TRUE**, values for the `offset` query param become opaque:\n
    - always start with `offset` == 0
    - only use the value for offset in the `next` key in the response for `offsets` for subsequent pages,
    otherwise some records might (probably will) be duplicated accross pages and/or skipped entirely
    """
    if query_only_active:
        users, explicit_offset = await pagination.get_in_memory_filtered(
            query_pagination.offset,
            query_pagination.limit,
            getter=partial(UsersService.get_many, NormalUser, limit=query_pagination.limit),
            filter=SessionsService.filter_out_inactive,
        )
    else:
        users = await UsersService.get_many(NormalUser, offset=query_pagination.offset, limit=query_pagination.limit)
        explicit_offset = None
    if users is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    return {
        "count": len(users),
        "next": pagination.http_offset_limit_next_link(
            req,
            len(users),
            explicit_offset,
        ),
        "data": users,
    }


@__router_users.get(
    "/deleted",
    status_code=status.HTTP_200_OK,
    response_model=ItemPaginated[AdminGetUserResponse],
    responses={
        # **admin_auth_exceptions,
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminAuthDependency],
)
async def get_users_deleted(
    query_pagination: PaginationOffsetLmitDependency,
    *,
    req: Request,
) -> ItemPaginated[NormalUser]:
    """Get all deleted normal `Users`.

    Results are available only if the current UsersProvider supports and implements `Users` soft-delete.
    """
    users = await UsersService.get_many(
        NormalUser, offset=query_pagination.offset, limit=query_pagination.limit, is_deleted=True
    )
    if users is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    return {
        "count": len(users),
        "next": pagination.http_offset_limit_next_link(req, len(users)),
        "data": users,
    }


@__router_users.get(
    "/{field}",
    status_code=status.HTTP_200_OK,
    response_model=Item[AdminGetUserResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": HTTPExceptionResponse},
        status.HTTP_404_NOT_FOUND: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminAuthDependency],
)
async def get_user(
    field: str,
    query_value: str = Query(alias="value"),
) -> Item[NormalUser]:
    """Get an existing `User` by a field value (e.g. by ID, or EMAIL, or USERNAME etc)."""
    if field not in NormalUser.fields_unique():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid field - allowed values are: {NormalUser.fields_unique()}",
        )
    user = await UsersService.get_unique_by(NormalUser, use_OR_clause=False, **{field: query_value})
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"data": user}


# @__router_admins_normal.get(
#     "/sessions/",
#     dependencies=[AdminAuthDependency],
# )
async def get_sessions_all(
    query_expired: bool = Query(alias="include_expired", default=False),
):
    """Get all or only the non-expired `Sessions` for all `Users`."""
    raise NotImplementedError()


@__router_users.get(
    "/sessions/{field}",
    status_code=status.HTTP_200_OK,
    response_model=ItemPaginated[AdminGetSessionResponse],
    dependencies=[AdminAuthDependency],
)
async def get_sessions(
    field: str,
    query_pagination: PaginationOffsetLmitDependency,
    query_value: str = Query(alias="value"),
    query_for: typing.Literal["admin", "user"] = Query(alias="for"),
    query_expired: bool = Query(alias="include_expired", default=False),
    *,
    req: Request,
) -> ItemPaginated[Session]:
    """Get all or only the non-expired `Sessions` for an ADMIN or a normal `User` by a field value (e.g by ID, or EMAIL, or USERNAME etc)."""
    model = AdminUser if query_for == "admin" else NormalUser
    if field not in model.fields_unique():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid field for {query_for.upper()} - allowed values are: {model.fields_unique()}",
        )
    user = await UsersService.get_unique_by(model, use_OR_clause=False, **{field: query_value})
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    sessions = await SessionsService.get_many(
        user.id, offset=query_pagination.offset, limit=query_pagination.limit, include_expired=query_expired
    )
    if sessions is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    return {
        "count": len(sessions),
        "next": pagination.http_offset_limit_next_link(req, len(sessions)),
        "data": sessions,
    }


####################
#   Main
####################

router_admins.include_router(__router_admins_super, prefix=_PATH_ADMIN, tags=[_TAG_ADMIN_SUPER])
router_admins.include_router(__router_admins_normal, prefix=_PATH_ADMIN, tags=[_TAG_ADMIN])
router_admins.include_router(__router_users, prefix=_PATH_USER, tags=[_TAG_ADMIN])
