import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import User
from app.security import (
    SESSION_COOKIE,
    CurrentUser,
    DatabaseSession,
    SessionToken,
    hash_password,
    limit_auth_attempts,
    require_request_header,
    revoke_session,
    start_session,
    verify_password,
)

router = APIRouter(
    prefix="/auth", tags=["Accounts"], dependencies=[Depends(require_request_header)]
)
EMAIL = re.compile(
    r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}"
)


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(max_length=254, examples=["person@example.com"])]
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not EMAIL.fullmatch(email) or len(email.split("@", 1)[0]) > 64:
            raise ValueError("Введите корректный email")
        return email


class Registration(Credentials):
    password: Annotated[SecretStr, Field(min_length=15, max_length=128)]


class Account(BaseModel):
    email: str | None
    demo: bool = False


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_auth_attempts)],
)
def register(
    data: Registration,
    request: Request,
    response: Response,
    db: DatabaseSession,
    token: SessionToken,
) -> Account:
    digest = hash_password(data.password.get_secret_value())
    user_id = db.scalar(
        insert(User)
        .values(email=data.email, password_hash=digest)
        .on_conflict_do_nothing(index_elements=[User.email])
        .returning(User.id)
    )
    if user_id is None:
        raise HTTPException(status_code=409, detail="Этот email уже зарегистрирован")

    start_session(db, user_id, token, response, secure=request.app.state.secure_cookies)
    return Account(email=data.email)


@router.post("/login", dependencies=[Depends(limit_auth_attempts)])
def login(
    data: Credentials,
    request: Request,
    response: Response,
    db: DatabaseSession,
    token: SessionToken,
) -> Account:
    user = db.scalar(select(User).where(User.email == data.email))
    digest = user.password_hash if user is not None else None
    valid = verify_password(data.password.get_secret_value(), digest)
    if user is None or not valid:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    account = Account(email=user.email)
    start_session(db, user.id, token, response, secure=request.app.state.secure_cookies)
    return account


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: DatabaseSession, token: SessionToken) -> Response:
    revoke_session(db, token)
    db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=request.app.state.secure_cookies,
        samesite="lax",
    )
    return response


@router.get("/me")
def read_account(user: CurrentUser) -> Account:
    if user.password_hash is None:
        return Account(email=None, demo=True)
    return Account(email=user.email)
