from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_session
from models import User
from schemas.user import Token, UserCreate, UserRead
from security import create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Аутентификация"])


@router.post("/register", response_model=UserRead, status_code=201,
             summary="Жаңа студентті тіркеу")
def register(data: UserCreate, db: Session = Depends(get_session)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Бұл email бұрын тіркелген")

    user = User(full_name=data.full_name.strip(), email=email,
                password_hash=generate_password_hash(data.password), role="student")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=Token, summary="Кіру және токен алу")
def login_for_token(form: OAuth2PasswordRequestForm = Depends(),
                    db: Session = Depends(get_session)):
    # Swagger-де "username" өрісіне email жазылады
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if user is None or not check_password_hash(user.password_hash, form.password):
        raise HTTPException(status_code=401, detail="Email немесе құпиясөз қате",
                            headers={"WWW-Authenticate": "Bearer"})
    return Token(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserRead, summary="Менің аккаунтым")
def me(user: User = Depends(get_current_user)):
    return user