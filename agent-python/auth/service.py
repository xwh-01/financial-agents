from fastapi import HTTPException, status

from auth import repository
from auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from auth.security import create_access_token, hash_password, verify_password


def register_user(req: RegisterRequest) -> UserResponse:
    if len(req.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    if repository.email_exists(req.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    password_hash = hash_password(req.password)
    user = repository.create_user(
        email=req.email,
        password_hash=password_hash,
        nickname=req.nickname,
    )
    return _to_user_response(user)


def login_user(req: LoginRequest) -> TokenResponse:
    user = repository.get_user_by_email(req.email)
    if user is None:
        raise _invalid_credentials()

    if user.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is not active",
        )

    if not verify_password(req.password, user["password_hash"]):
        raise _invalid_credentials()

    return TokenResponse(access_token=create_access_token(user_id=user["id"]))


def get_user_by_id(user_id: int) -> UserResponse:
    user = repository.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return _to_user_response(user)


def _to_user_response(user: dict) -> UserResponse:
    return UserResponse(
        id=user["id"],
        email=user["email"],
        nickname=user.get("nickname"),
        status=user.get("status"),
    )


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
