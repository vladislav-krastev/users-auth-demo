from fastapi import HTTPException, status

from api_rest.schemas.common import HTTPExceptionResponse


SERVICE_UNAVAILABLE_EXCEPTION = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="The request cannot be completed. Please, try again later.",
)
"""An `HTTPException` with status `503`."""


base_auth_exceptions = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": HTTPExceptionResponse,
        "description": "Could not validate credentials",
    },
    status.HTTP_404_NOT_FOUND: {
        "model": HTTPExceptionResponse,
        "description": "User not found",
    },
}
"""Possible `HTTPException` Responses while getting any `User`."""


user_auth_exceptions = {
    **base_auth_exceptions,
    status.HTTP_403_FORBIDDEN: {
        "model": HTTPExceptionResponse,
        "description": "Operation not allowed for User",
    },
}
"""Possible `HTTPException` Responses while getting the current `User`."""


admin_auth_exceptions = {
    **base_auth_exceptions,
    status.HTTP_403_FORBIDDEN: {
        "model": HTTPExceptionResponse,
        "description": "User is not an ADMIN",
    },
}
"""Possible `HTTPException` Responses while getting the current ADMIN `User`"""
