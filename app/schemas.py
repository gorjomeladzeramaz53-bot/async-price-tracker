from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class ProductBase(BaseModel):
    title: str
    url: str

class ProductCreate(ProductBase):
    target_price: float  # <--- თუ target_price-ს ითხოვ შექმნისას, აქაც უნდა იყოს!

class ProductResponse(ProductBase):
    id: int
    current_price: Optional[float] = None
    target_price: float
    is_in_stock: Optional[bool] = True
    last_checked: Optional[datetime] = None  # <--- გახდა არასავალდებულო

    class Config:
        from_attributes = True

class PriceHistoryResponse(BaseModel):
    id: int
    product_id: int
    price: float
    timestamp: datetime

    class Config:
        from_attributes = True