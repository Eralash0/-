from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Тіркелу кезінде келетін деректер. Бәрі автоматты тексеріледі."""
    full_name: str = Field(min_length=2, max_length=100, examples=["Мустафа Ерасыл"])
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserRead(BaseModel):
    """Жауап ретінде қайтарылатын деректер. Құпиясөз ешқашан қайтарылмайды."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: str
    created_at: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"