import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from database import get_session
from models import Category, Test
from schemas.category import CategoryRead
from schemas.common import Page
from schemas.test import TestRead, to_test_read

router = APIRouter(prefix="/api", tags=["Каталог"])


@router.get("/categories", response_model=list[CategoryRead],
            summary="Санаттар тізімі")
def list_categories(db: Session = Depends(get_session)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.get("/tests", response_model=Page[TestRead],
            summary="Тесттер каталогы: беттеу, іздеу, сүзгі, сұрыптау")
def list_tests(
    page: int = Query(1, ge=1, description="Бет нөмірі"),
    size: int = Query(6, ge=1, le=50, description="Бетте неше тест"),
    q: str | None = Query(None, max_length=100, description="Атауы бойынша іздеу"),
    category_id: int | None = Query(None, description="Санат бойынша сүзу"),
    min_score: int | None = Query(None, ge=1, description="Ең аз максималды балл"),
    max_score: int | None = Query(None, le=1000, description="Ең көп максималды балл"),
    sort: Literal["id", "title", "max_score"] = Query("id", description="Сұрыптау өрісі"),
    order: Literal["asc", "desc"] = Query("desc", description="Сұрыптау бағыты"),
    db: Session = Depends(get_session),
):
    # Тек сұрағы бар тесттер көрсетіледі
    stmt = select(Test).where(Test.questions.any())

    if q:
        stmt = stmt.where(Test.title.ilike(f"%{q.strip()}%"))
    if category_id is not None:
        stmt = stmt.where(Test.category_id == category_id)
    if min_score is not None:
        stmt = stmt.where(Test.max_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(Test.max_score <= max_score)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    column = {"id": Test.id, "title": Test.title, "max_score": Test.max_score}[sort]
    column = column.asc() if order == "asc" else column.desc()

    items = db.scalars(
        stmt.order_by(column)
        .offset((page - 1) * size)
        .limit(size)
        .options(selectinload(Test.category), selectinload(Test.questions))
    ).all()

    return Page[TestRead](
        items=[to_test_read(t) for t in items],
        total=total,
        page=page,
        size=size,
        pages=max(1, math.ceil(total / size)),
    )


@router.get("/tests/{test_id}", response_model=TestRead,
            summary="Тесттің толық сипаттамасы")
def get_test(test_id: int, db: Session = Depends(get_session)):
    test = db.scalar(
        select(Test).where(Test.id == test_id)
        .options(selectinload(Test.category), selectinload(Test.questions))
    )
    if test is None:
        raise HTTPException(status_code=404, detail="Тест табылмады")
    return to_test_read(test)