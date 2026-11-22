import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_session
from models import User

SECRET_KEY = os.getenv("JWT_SECRET", "change-this-jwt-secret-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 60
COOKIE_NAME = "access_token"

# Swagger-дегі "Authorize" батырмасы осы жолға сұрау жібереді
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def create_access_token(user_id: int, role: str) -> str:
    """Қолданушы id-і мен рөлі жазылған, қолтаңбасы бар токен жасайды."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request,
                     token: str | None = Depends(oauth2_scheme),
                     db: Session = Depends(get_session)) -> User:
    """Токенді Authorization тақырыбынан немесе cookie-дан алып, қолданушыны табады."""
    token = token or request.cookies.get(COOKIE_NAME)
    if not token:
        raise _unauthorized("Токен жоқ, алдымен кіріңіз")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Токен мерзімі біткен, қайта кіріңіз")
    except jwt.InvalidTokenError:
        raise _unauthorized("Токен жарамсыз")

    user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    if user is None:
        raise _unauthorized("Қолданушы табылмады")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Тек әкімшіге рұқсат")
    return user