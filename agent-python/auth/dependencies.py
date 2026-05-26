from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import repository
from auth.schemas import UserResponse
from auth.security import TokenError, decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Missing bearer token")

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise _unauthorized(str(exc)) from exc

    user_id = payload.get("user_id")
    if user_id is None:
        raise _unauthorized("Token payload missing user_id")

    user = repository.get_user_by_id(int(user_id))
    if user is None:
        raise _unauthorized("User not found")

    return UserResponse(
        id=user["id"],
        email=user["email"],
        nickname=user.get("nickname"),
        status=user.get("status"),
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
