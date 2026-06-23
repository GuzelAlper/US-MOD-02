# app/schemas/queue.py
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID

class QueueClaimRequest(BaseModel):
    queue_id: Optional[int] = Field(None, ge=1, le=4, description="1-4 arası öncelik sırası")
    # 🚨 DÜZELTİLDİ: int listesi yerine OpenAPI kontratına tam uyumlu UUID string/object listesi yapıldı
    category_ids: Optional[List[UUID]] = Field(None, description="Filtrelenecek kategori UUID listesi")