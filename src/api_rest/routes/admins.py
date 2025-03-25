import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException, Query, Request, status

from api_rest.dependencies import (
    AdminAuthDependency,
    AdminSuperAuthDependency,
    AdminUserDependency,
    PaginationOffsetLmitDependency,
)
from api_rest.exceptions import SERVICE_UNAVAILABLE_EXCEPTION
from api_rest.schemas.admins import AdminCreateRequest, AdminShortResponse
from api_rest.schemas.common import HTTPExceptionResponse, Item, ItemPaginated
from config.app import AppConfig, _AppConfig
from services.sessions import SessionsService
from services.users import AdminUser, UsersService
from utils import pagination, password


PATH_ADMINS = "admins"
TAG_ADMINS = "Admin"
TAG_ADMINS_SUPER = "Super Admin"


router_admins = APIRouter()


##############################
#   with SUPER ADMIN auth
##############################


@router_admins.get(
    "/config",
    tags=[TAG_ADMINS_SUPER],
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminSuperAuthDependency],
)
async def get_current_config() -> Item[_AppConfig]:
    """Get the currently applied configurations."""
    return {"data": AppConfig}


__router_admins_super = APIRouter(
    prefix=f"/{PATH_ADMINS}",
    tags=[TAG_ADMINS_SUPER],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminSuperAuthDependency],
)


@__router_admins_super.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=Item[AdminShortResponse],
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


# @__router_admins_normal.get(
#     "/logins/",
#     status_code=status.HTTP_200_OK,
#     response_model=ItemPaginated[AdminGetSessionResponse],
#     dependencies=[AdminAuthDependency],
# )
async def get_logins():
    pass


##############################
#   with any ADMIN auth
##############################

__router_admins = APIRouter(
    prefix=f"/{PATH_ADMINS}",
    tags=[TAG_ADMINS],
)


@__router_admins.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=ItemPaginated[AdminShortResponse],
    responses={
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


@__router_admins.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=Item[AdminShortResponse],
)
async def get_me(*, auth: AdminUserDependency) -> Item[AdminUser]:
    """Get current ADMIN."""
    return {"data": auth.user}


@__router_admins.get(
    "/{username}",
    status_code=status.HTTP_200_OK,
    response_model=Item[AdminShortResponse],
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


##############################
#   register routes
##############################

router_admins.include_router(__router_admins_super)
router_admins.include_router(__router_admins)
