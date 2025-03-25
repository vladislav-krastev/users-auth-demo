import typing

from fastapi import APIRouter, HTTPException, Query, Request, status

from api_rest.dependencies import AdminAuthDependency, AdminSuperAuthDependency, PaginationOffsetLmitDependency
from api_rest.exceptions import SERVICE_UNAVAILABLE_EXCEPTION
from api_rest.schemas.common import HTTPExceptionResponse, ItemPaginated
from api_rest.schemas.sessions import SessionFullResponse
from services.sessions import Session, SessionsService
from services.users import AdminUser, NormalUser, UsersService
from utils import pagination


PATH_SESSIONS = "sessions"
TAG_ADMINS = "Admin"
TAG_ADMINS_SUPER = "Super Admin"


router_sessions = APIRouter()


##############################
#   with SUPER ADMIN auth
##############################

__router_admins_super = APIRouter(
    prefix=f"/{PATH_SESSIONS}",
    tags=[TAG_ADMINS_SUPER],
    responses={
        status.HTTP_403_FORBIDDEN: {"model": HTTPExceptionResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HTTPExceptionResponse},
    },
    dependencies=[AdminSuperAuthDependency],
)


@__router_admins_super.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def invalidate_sessions_all(
    user_id: str,
) -> None:
    """Invalidate all `Sessions` of the `User` with ID `user_id`."""
    if not await SessionsService.invalidate_all(user_id):
        raise SERVICE_UNAVAILABLE_EXCEPTION


@__router_admins_super.delete(
    "/{user_id}/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def invalidate_sessions_single(
    user_id: str,
    session_id: str,
) -> None:
    """Invalidate the `Session` with ID `session_id` of the `User` with ID `user_id`."""
    if not await SessionsService.invalidate(user_id, session_id):
        raise SERVICE_UNAVAILABLE_EXCEPTION


##############################
#   with any ADMIN auth
##############################

__router_admins = APIRouter(
    prefix=f"/{PATH_SESSIONS}",
    tags=[TAG_ADMINS],
    dependencies=[AdminAuthDependency],
)


# @__router_admins_normal.get(
#     "/sessions/",
#     dependencies=[AdminAuthDependency],
# )
async def get_sessions_all(
    query_expired: bool = Query(alias="include_expired", default=False),
):
    """Get all or only the non-expired `Sessions` for all `Users`."""
    raise NotImplementedError()


@__router_admins.get(
    "/{field}",
    status_code=status.HTTP_200_OK,
    response_model=ItemPaginated[SessionFullResponse],
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


##############################
#   register routes
##############################

router_sessions.include_router(__router_admins_super)
router_sessions.include_router(__router_admins)
