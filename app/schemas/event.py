from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ProductPayload(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    queue_priority: Optional[int] = None
    json_after: Optional[dict] = None

class ProductEvent(BaseModel):
    event_type: str
    product_id: str
    seller_id: Optional[str] = None
    idempotency_key: str
    occurred_at: datetime
    payload: ProductPayload

    class Config:
        populate_by_name = True