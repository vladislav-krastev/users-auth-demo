import asyncio

from fastapi import APIRouter, HTTPException, status

from api_rest.dependencies import NormalUserDependency
from api_rest.exceptions import SERVICE_UNAVAILABLE_EXCEPTION, user_auth_exceptions
from api_rest.schemas.common import HTTPExceptionResponse, Item
from api_rest.schemas.users import (
    UserBaseResponse,
    UserUpdatePasswordRequest,
    UserUpdateRequest,
)
from config import AppConfig
from services.sessions import SessionsService
from services.users import NormalUser, UsersService
from utils import password


_PATH_USER = "/users"
_TAG_USER = "User"


router_users = APIRouter(
    tags=[_TAG_USER],
    prefix=_PATH_USER,
    responses={**user_auth_exceptions},
)


@router_users.get(
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


@router_users.patch(
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


@router_users.patch(
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


@router_users.delete(
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
