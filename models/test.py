from sqlalchemy import ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Category(Base):
    """Санат (пән): «Python», «Математика» және т.б."""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    tests = relationship("Test", back_populates="category")


class Test(Base):
    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False, default=100,
                                           server_default="100")
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20,
                                                  server_default="20")
    created_at: Mapped[str | None] = mapped_column(String,
                                                   server_default=func.current_timestamp())
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    category = relationship("Category", back_populates="tests")
    questions = relationship("Question", back_populates="test",
                             cascade="all, delete-orphan", order_by="Question.id")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"),
                                         nullable=False)
    question_text: Mapped[str] = mapped_column(String, nullable=False)
    option_a: Mapped[str] = mapped_column(String, nullable=False)
    option_b: Mapped[str] = mapped_column(String, nullable=False)
    option_c: Mapped[str] = mapped_column(String, nullable=False)
    option_d: Mapped[str] = mapped_column(String, nullable=False)
    correct_option: Mapped[str] = mapped_column(String, nullable=False)

    test = relationship("Test", back_populates="questions")