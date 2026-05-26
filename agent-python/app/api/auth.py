from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from auth.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from auth.service import login_user, register_user


router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register_route(request: RegisterRequest):
    return register_user(request)


@router.post("/login", response_model=TokenResponse)
async def login_route(request: LoginRequest):
    return login_user(request)


@router.get("/me", response_model=UserResponse)
async def me_route(current_user: UserResponse = Depends(get_current_user)):
    return current_user
