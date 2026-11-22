from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from database import get_session
from models import CartItem, Test, User
from schemas.cart import CartAdd, CartItemRead, CartRead
from schemas.test import to_test_read
from security import get_current_user

router = APIRouter(prefix="/api/cart", tags=["Себет"])


def _cart_query(user_id: int):
    return (
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .options(selectinload(CartItem.test).selectinload(Test.questions),
                 selectinload(CartItem.test).selectinload(Test.category))
        .order_by(CartItem.id)
    )


def _cart_read(db: Session, user_id: int) -> CartRead:
    rows = db.scalars(_cart_query(user_id)).all()
    items = [CartItemRead(id=r.id, quantity=r.quantity, test=to_test_read(r.test))
             for r in rows]
    return CartRead(items=items, count=len(items))


@router.get("", response_model=CartRead, summary="Менің себетім")
def get_cart(db: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    return _cart_read(db, user.id)


@router.post("", response_model=CartRead, status_code=status.HTTP_201_CREATED,
             summary="Себетке тест қосу")
def add_to_cart(data: CartAdd, db: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    test = db.get(Test, data.test_id)
    if test is None:
        raise HTTPException(status_code=404, detail="Тест табылмады")
    if not test.questions:
        raise HTTPException(status_code=400, detail="Бұл тестте сұрақ жоқ")

    exists = db.scalar(select(CartItem).where(
        CartItem.user_id == user.id, CartItem.test_id == test.id))
    if exists:
        raise HTTPException(status_code=409, detail="Бұл тест себетте бар")

    db.add(CartItem(user_id=user.id, test_id=test.id, quantity=1))
    db.commit()
    return _cart_read(db, user.id)


@router.delete("/{test_id}", status_code=204, summary="Себеттен тестті өшіру")
def remove_from_cart(test_id: int, db: Session = Depends(get_session),
                     user: User = Depends(get_current_user)):
    item = db.scalar(select(CartItem).where(
        CartItem.user_id == user.id, CartItem.test_id == test_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Себетте мұндай тест жоқ")
    db.delete(item)
    db.commit()


@router.delete("", status_code=204, summary="Себетті толық тазалау")
def clear_cart(db: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    db.execute(delete(CartItem).where(CartItem.user_id == user.id))
    db.commit()