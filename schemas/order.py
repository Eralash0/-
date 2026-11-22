from pydantic import BaseModel


class OrderItemRead(BaseModel):
    id: int
    test_id: int
    test_title: str
    quantity: int
    result_id: int | None = None


class OrderRead(BaseModel):
    id: int
    status: str            # "pending" — күтуде, "done" — барлық тест тапсырылған
    created_at: str | None = None
    items: list[OrderItemRead]