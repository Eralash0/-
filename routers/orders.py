from fastapi import APIRouter, Depends, HTTPException, status
router = APIRouter(prefix="/api/orders", tags=["Тапсырыстар"])
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database import SessionLocal, get_session
from models import CartItem, Order, OrderItem, User
from schemas.order import OrderItemRead, OrderRead
from security import get_current_user

router = APIRouter(prefix="/api/orders", tags=["Тапсырыстар"])


def _order_query():
    return select(Order).options(selectinload(Order.items).selectinload(OrderItem.test))


def order_to_read(order: Order) -> OrderRead:
    return OrderRead(
        id=order.id,
        status=order.status,
        created_at=order.created_at,
        items=[OrderItemRead(id=i.id, test_id=i.test_id, test_title=i.test.title,
                             quantity=i.quantity, result_id=i.result_id)
               for i in order.items],
    )


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED,
             summary="Себетті тапсырысқа айналдыру (рәсімдеу)")
def checkout(db: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    carts = db.scalars(select(CartItem).where(CartItem.user_id == user.id)).all()
    if not carts:
        raise HTTPException(status_code=400, detail="Себет бос")

    order = Order(user_id=user.id, status="pending")
    order.items = [OrderItem(test_id=c.test_id, quantity=c.quantity) for c in carts]
    db.add(order)
    for c in carts:
        db.delete(c)
    db.commit()

    order = db.scalar(_order_query().where(Order.id == order.id))
    return order_to_read(order)


@router.get("", response_model=list[OrderRead], summary="Менің тапсырыстарым (тарих)")
def my_orders(db: Session = Depends(get_session),
              user: User = Depends(get_current_user)):
    rows = db.scalars(
        _order_query().where(Order.user_id == user.id).order_by(Order.id.desc())
    ).all()
    return [order_to_read(o) for o in rows]


@router.get("/{order_id}", response_model=OrderRead, summary="Тапсырыс мәліметі")
def get_order(order_id: int, db: Session = Depends(get_session),
              user: User = Depends(get_current_user)):
    order = db.scalar(_order_query().where(Order.id == order_id))
    if order is None:
        raise HTTPException(status_code=404, detail="Тапсырыс табылмады")
    if order.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="Рұқсат жоқ")
    return order_to_read(order)


def attach_result(user_id: int, test_id: int, result_id: int) -> None:
    """Студент тестті тапсырғанда, тапсырыстағы сәйкес жолды нәтижеге байлайды.
    Барлық жол байланған болса, тапсырыс күйі «done» болады."""
    with SessionLocal() as db:
        item = db.scalar(
            select(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.user_id == user_id,
                   OrderItem.test_id == test_id,
                   OrderItem.result_id.is_(None))
            .order_by(OrderItem.id)
        )
        if item is None:
            return
        item.result_id = result_id
        order = item.order
        if all(i.result_id is not None for i in order.items):
            order.status = "done"
        db.commit()