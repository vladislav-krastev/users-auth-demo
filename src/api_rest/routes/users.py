import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException, Query, Request, status

from api_rest.dependencies import AdminAuthDependency, NormalUserDependency, PaginationOffsetLmitDependency
from api_rest.exceptions import SERVICE_UNAVAILABLE_EXCEPTION, user_auth_exceptions
from api_rest.schemas.admins import AdminGetUserResponse
from api_rest.schemas.common import HTTPExceptionResponse, Item, ItemPaginated
from api_rest.schemas.users import UserBaseResponse, UserUpdatePasswordRequest, UserUpdateRequest
from config import AppConfig
from services.sessions import SessionsService
from services.users import NormalUser, UsersService
from utils import pagination, password


PATH_USERS = "users"
TAG_ADMINS = "Admin"
TAG_USERS = "User"


router_users = APIRouter()


##############################
#   with normal ADMIN auth
##############################

__router_admins = APIRouter(
    prefix=f"/{PATH_USERS}",
    tags=[TAG_ADMINS],
    dependencies=[AdminAuthDependency],
)


@__router_admins.get(
    "/",
    status_code=status.HTTP_200_OK,
    response_model=ItemPaginated[AdminGetUserResponse],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
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


@__router_admins.get(
    "/deleted",
    status_code=status.HTTP_200_OK,
    response_model=ItemPaginated[AdminGetUserResponse],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
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


@__router_admins.get(
    "/{field}",
    status_code=status.HTTP_200_OK,
    response_model=Item[AdminGetUserResponse],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": HTTPExceptionResponse},
        status.HTTP_404_NOT_FOUND: {"model": HTTPExceptionResponse},
    },
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


##############################
#   with USERS auth
##############################

__router_users = APIRouter(
    prefix=f"/{PATH_USERS}",
    tags=[TAG_USERS],
    responses={**user_auth_exceptions},
)


@__router_users.get(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=Item[UserBaseResponse],
)
async def get_me(
    *,
    auth: NormalUserDependency,
) -> Item[NormalUser]:
    """Get current `User`."""
    return {"data": auth.user}


@__router_users.patch(
    "/me",
    status_code=status.HTTP_200_OK,
    response_model=Item[UserBaseResponse],
    responses={
        status.HTTP_409_CONFLICT: {"model": HTTPExceptionResponse},
    },
)
async def update_me(
    body: UserUpdateRequest,
    *,
    auth: NormalUserDependency,
) -> Item[NormalUser]:
    """Update current `User`."""
    fields_to_update = {
        attr_key: getattr(body, attr_key)
        for attr_key in body.model_fields_set
        if getattr(auth.user, attr_key) != getattr(body, attr_key)
    }
    if not fields_to_update:
        return {"data": auth.user}
    fields_to_update_unique = {k: v for k, v in fields_to_update.items() if k in NormalUser.fields_unique()}
    existing = await UsersService.get_many(
        NormalUser,
        limit=2,
        use_OR_clause=True,
        **fields_to_update_unique,
    )
    if existing is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    if len(existing) > 1 or (len(existing) == 1 and existing[0].id != auth.user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            # TODO: this msg is not only ugly, but also wrong:
            detail=f"A user with this {fields_to_update_unique.keys()} already exists.",
        )
    updated = await UsersService.update(NormalUser, user_id=auth.user.id, **fields_to_update)
    if updated is None:
        raise SERVICE_UNAVAILABLE_EXCEPTION
    return {"data": updated}


@__router_users.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": HTTPExceptionResponse},
    },
)
async def update_my_password(
    body: UserUpdatePasswordRequest,
    *,
    auth: NormalUserDependency,
) -> None:
    """Update password of current `User`."""
    if not AppConfig.LOCAL_AUTH.IS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local authentication with a password is not allowed.",
        )
    if auth.user.password is not None:  # may be NONE for first-time pswd change from an externally registered user
        if body.current_password is None or not password.hash_verify(body.current_password, auth.user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect password.",
            )
        if body.current_password == body.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New and current passwords cannot be the same.",
            )
    updated = await UsersService.update(
        NormalUser, user_id=auth.user.id, password=password.hash_create(body.new_password)
    )
    if updated is None or (auth.user.password is not None and updated.password == auth.user.password):
        raise SERVICE_UNAVAILABLE_EXCEPTION


@__router_users.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_me(
    *,
    auth: NormalUserDependency,
) -> None:
    """Delete current `User`."""
    # a user should be able to always delete themself, even if session invalidation failed:
    asyncio.create_task(SessionsService.invalidate_all(auth.user.id))
    # ... and even if user-deletion failed:
    asyncio.create_task(UsersService.delete(auth.user.id))


##############################
#   register routes
##############################

router_users.include_router(__router_admins)
router_users.include_router(__router_users)
