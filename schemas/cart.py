from pydantic import BaseModel, Field

from schemas.test import TestRead


class CartAdd(BaseModel):
    test_id: int = Field(gt=0, examples=[1])


class CartItemRead(BaseModel):
    id: int
    quantity: int
    test: TestRead


class CartRead(BaseModel):
    items: list[CartItemRead]
    count: int