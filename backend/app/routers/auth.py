from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, issue_session
from app.config import settings
from app.db import get_db
from app.models.entities import LoginSession, User
from app.models.schemas import Credentials, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
password_hasher = PasswordHasher()


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_hours * 3600,
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    user = User(email=payload.email, password_hash=password_hasher.hash(payload.password))
    db.add(user)
    try:
        db.flush()
        token, _ = issue_session(db, user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    set_auth_cookie(response, token)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    try:
        password_hasher.verify(user.password_hash, payload.password)
    except (VerifyMismatchError, VerificationError):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = password_hasher.hash(payload.password)
    token, _ = issue_session(db, user)
    set_auth_cookie(response, token)
    return user


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_session = getattr(request.state, "auth_session", None)
    if auth_session:
        auth_session.revoked_at = datetime.now(timezone.utc)
        db.commit()
    response.delete_cookie("access_token", path="/", httponly=True, samesite="lax")
    return response
