import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.entities import LoginSession, User


def issue_session(db: Session, user: User) -> tuple[str, LoginSession]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.access_token_hours)
    token_id = uuid.uuid4().hex
    token = jwt.encode(
        {"sub": str(user.id), "jti": token_id, "iat": now, "exp": expires_at},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    session = LoginSession(user_id=user.id, token_id=token_id, expires_at=expires_at)
    db.add(session)
    db.commit()
    return token, session


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = uuid.UUID(payload["sub"])
        token_id = payload["jti"]
    except (JWTError, KeyError, ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")

    now = datetime.now(timezone.utc)
    auth_session = db.scalar(
        select(LoginSession).where(
            LoginSession.token_id == token_id,
            LoginSession.user_id == user_id,
            LoginSession.revoked_at.is_(None),
            LoginSession.expires_at > now,
        )
    )
    user = db.get(User, user_id)
    if auth_session is None or user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active.")
    request.state.auth_session = auth_session
    return user
