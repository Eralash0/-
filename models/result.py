from sqlalchemy import Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class Result(Base):
    """Студенттің тест нәтижесі."""
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"),
                                         nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)
    percent: Mapped[float] = mapped_column(Float, nullable=False)
    taken_at: Mapped[str | None] = mapped_column(String,
                                                 server_default=func.current_timestamp())

    user = relationship("User", back_populates="results")
    test = relationship("Test")
    answers = relationship("ResultAnswer", back_populates="result",
                           cascade="all, delete-orphan", order_by="ResultAnswer.position")


class ResultAnswer(Base):
    """Нәтиже кезіндегі сұрақтың көшірмесі және студенттің жауабы."""
    __tablename__ = "result_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("results.id", ondelete="CASCADE"),
                                           nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(String, nullable=False)
    option_a: Mapped[str] = mapped_column(String, nullable=False)
    option_b: Mapped[str] = mapped_column(String, nullable=False)
    option_c: Mapped[str] = mapped_column(String, nullable=False)
    option_d: Mapped[str] = mapped_column(String, nullable=False)
    correct_option: Mapped[str] = mapped_column(String, nullable=False)
    chosen_option: Mapped[str | None] = mapped_column(String)

    result = relationship("Result", back_populates="answers")