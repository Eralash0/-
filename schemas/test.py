from pydantic import BaseModel, ConfigDict, Field

from schemas.category import CategoryRead


class TestCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120, examples=["Python негіздері"])
    description: str | None = Field(default=None, max_length=300)
    max_score: int = Field(default=100, ge=1, le=1000)
    duration_minutes: int = Field(default=20, ge=1, le=180)
    category_id: int | None = None


class TestUpdate(BaseModel):
    """Өзгерту үшін барлық өрістер міндетті емес."""
    title: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    max_score: int | None = Field(default=None, ge=1, le=1000)
    duration_minutes: int | None = Field(default=None, ge=1, le=180)
    category_id: int | None = None


class TestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    max_score: int
    duration_minutes: int
    category: CategoryRead | None = None
    questions_count: int = 0


def to_test_read(test) -> TestRead:
    """ORM объектісін жауап схемасына айналдырады, сұрақтар санын қосады."""
    data = TestRead.model_validate(test)
    data.questions_count = len(test.questions)
    return data