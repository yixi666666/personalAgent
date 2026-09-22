from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from agent.models.auth import LoginRequest, RegisterRequest, UserResponse
from agent.services.auth import (
    AUTH_COOKIE_NAME,
    create_auth_cookie,
    get_auth_service,
    get_current_user,
)


router = APIRouter()


def _set_auth_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=create_auth_cookie(user_id),
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response):
    try:
        user = get_auth_service().register(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _set_auth_cookie(response, user["id"])
    return user


@router.post("/auth/login", response_model=UserResponse)
def login(payload: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else None
    try:
        user = get_auth_service().login(payload.username, payload.password, client_ip)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    _set_auth_cookie(response, user["id"])
    return user


@router.get("/auth/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=False,
        samesite="lax",
    )
