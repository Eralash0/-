from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_session
from models import Category, Test, User
from schemas.category import CategoryCreate, CategoryRead
from schemas.test import TestCreate, TestRead, TestUpdate, to_test_read
from security import require_admin

# Бұл роутердің барлық маршрутына әкімші құқығы керек
router = APIRouter(prefix="/api/admin", tags=["Әкімші"],
                   dependencies=[Depends(require_admin)])


# ---------- Санаттар ----------

@router.post("/categories", response_model=CategoryRead, status_code=201,
             summary="Санат қосу")
def create_category(data: CategoryCreate, db: Session = Depends(get_session)):
    category = Category(name=data.name.strip())
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Бұл санат бұрын қосылған")
    db.refresh(category)
    return category


@router.put("/categories/{category_id}", response_model=CategoryRead,
            summary="Санатты өзгерту")
def update_category(category_id: int, data: CategoryCreate,
                    db: Session = Depends(get_session)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Санат табылмады")
    category.name = data.name.strip()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Бұл атаудағы санат бар")
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204,
               summary="Санатты өшіру")
def delete_category(category_id: int, db: Session = Depends(get_session)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Санат табылмады")
    # Санаттағы тесттер өшірілмейді, олардың category_id өрісі бос болады
    db.delete(category)
    db.commit()


# ---------- Тесттер ----------

@router.post("/tests", response_model=TestRead, status_code=201,
             summary="Тест қосу")
def create_test(data: TestCreate, db: Session = Depends(get_session),
                admin: User = Depends(require_admin)):
    if data.category_id is not None and db.get(Category, data.category_id) is None:
        raise HTTPException(status_code=404, detail="Санат табылмады")
    test = Test(**data.model_dump(), created_by=admin.id)
    db.add(test)
    db.commit()
    db.refresh(test)
    return to_test_read(test)


@router.put("/tests/{test_id}", response_model=TestRead,
            summary="Тестті өзгерту")
def update_test(test_id: int, data: TestUpdate, db: Session = Depends(get_session)):
    test = db.get(Test, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Тест табылмады")

    # Тек жіберілген өрістер өзгереді
    changes = data.model_dump(exclude_unset=True)
    if changes.get("category_id") is not None and db.get(Category, changes["category_id"]) is None:
        raise HTTPException(status_code=404, detail="Санат табылмады")

    for field, value in changes.items():
        setattr(test, field, value)
    db.commit()
    db.refresh(test)
    return to_test_read(test)


@router.delete("/tests/{test_id}", status_code=204, summary="Тестті өшіру")
def delete_test(test_id: int, db: Session = Depends(get_session)):
    test = db.get(Test, test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Тест табылмады")
    db.delete(test)
    db.commit()