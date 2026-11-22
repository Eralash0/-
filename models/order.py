from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class CartItem(Base):
    """Себеттегі тест. Бір студент бір тестті бір рет қосады."""
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "test_id", name="uq_cart_user_test"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"),
                                         nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                          server_default="1")

    test = relationship("Test")


class Order(Base):
    """Рәсімделген тапсырыс. Күйі: pending (күтуде) немесе done (аяқталды)."""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending",
                                        server_default="pending")
    created_at: Mapped[str | None] = mapped_column(String,
                                                   server_default=func.current_timestamp())

    items = relationship("OrderItem", back_populates="order",
                         cascade="all, delete-orphan", order_by="OrderItem.id")


class OrderItem(Base):
    """Тапсырыстағы тест. Тест тапсырылғанда result_id толтырылады."""
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"),
                                          nullable=False)
    test_id: Mapped[int] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"),
                                         nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1,
                                          server_default="1")
    result_id: Mapped[int | None] = mapped_column(
        ForeignKey("results.id", ondelete="SET NULL"), nullable=True)

    order = relationship("Order", back_populates="items")
    test = relationship("Test")
    result = relationship("Result")