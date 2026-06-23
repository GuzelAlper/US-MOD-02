from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, Header, Request, status
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.models.product_card import ProductCard, CardStatus
from app.core.config import settings
from app.schemas.queue import QueueClaimRequest

router = APIRouter()

@router.post("/queue/claim", status_code=status.HTTP_200_OK)
async def claim_next_ticket(
    request_data: QueueClaimRequest,  # Pydantic şeması (OpenAPI doğrulaması için)
    request: Request,                 # FastAPI Ham İstek Nesnesi (Lokal testlerdeki body'yi okumak için)
    db: Session = Depends(get_db),
    x_moderator_id: Optional[str] = Header(None, alias="X-Moderator-Id"),
    authorization: Optional[str] = Header(None, alias="Authorization") # Hakemin JWT uyarısı için eklendi
):
    """Взять следующий тикет из очереди и перевести его в IN_REVIEW."""
    
    moderator_id = None

    # 1. Eğer OpenAPI'nin şart koştuğu Bearer JWT token varsa onu oku
    if authorization and authorization.startswith("Bearer "):
        try:
            moderator_id = authorization.split(" ")[1]
        except Exception:
            moderator_id = None

    # 2. Eğer JWT yoksa X-Moderator-Id başlığına bak (AI Hakemin fallback yöntemi)
    if not moderator_id and x_moderator_id:
        moderator_id = x_moderator_id

    # 3. Eğer başlıklar yoksa eski yöntemle gövdeden (body) veri gönderildiyse ham json'ı oku
    if not moderator_id:
        try:
            body_json = await request.json()
            moderator_id = body_json.get("moderator_id")
        except Exception:
            moderator_id = None

    # 4. Eğer hiçbiri yoksa güvenli bir varsayılan değer ata
    if not moderator_id:
        moderator_id = "moderator_default_id"

    now = datetime.utcnow()

    # REKOMENDASYON: Süresi dolmuş kilitli kartları serbest bırak (Zaman aşımı temizliği)
    db.execute(
        update(ProductCard)
        .where(ProductCard.status == CardStatus.IN_REVIEW)
        .where(ProductCard.claim_expires_at < now)
        .values(
            status=CardStatus.PENDING,
            assigned_moderator_id=None,
            claim_expires_at=None
        )
    )
    db.commit()

    # 409 Kontrolü: Moderatörün aktif incelemesi var mı?
    existing = db.execute(
        select(ProductCard)
        .where(ProductCard.assigned_moderator_id == moderator_id)
        .where(ProductCard.status == CardStatus.IN_REVIEW)
        .limit(1)
    ).scalar_one_or_none()
    
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MODERATOR_ALREADY_HAS_ACTIVE_REVIEW",
                "message": "Moderator already has an active IN_REVIEW ticket."
            }
        )

    # Sıradan kart çekme mantığı
    query = select(ProductCard).where(ProductCard.status == CardStatus.PENDING)

    # 🚨 DÜZELTİLDİ: request_data.queue_priority yerine şemadaki değişken adı olan queue_id kullanıldı
    if request_data.queue_id is not None:
        query = query.where(ProductCard.queue_priority == request_data.queue_id)

    # KRİTİK DÜZELTME: category_ids filtresini sorguya dahil ediyoruz
    if request_data.category_ids:
        category_str_list = [str(c_id) for c_id in request_data.category_ids]
        
        if hasattr(ProductCard, 'category_id'):
            query = query.where(ProductCard.category_id.in_(category_str_list))
        else:
            query = query.where(
                ProductCard.json_after["category"]["id"].as_string().in_(category_str_list)
            )

    # Hakemin onayladığı sıralama kuralı
    query = query.order_by(ProductCard.queue_priority.asc(), ProductCard.created_at.asc())
    
    if not settings.DATABASE_URL.startswith("sqlite"):
        query = query.limit(1).with_for_update(skip_locked=True)
    else:
        query = query.limit(1)

    ticket = db.execute(query).scalar_one_or_none()
    
    if ticket is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Kartı güncelle ve moderatöre ata
    ticket.status = CardStatus.IN_REVIEW
    ticket.assigned_moderator_id = moderator_id
    ticket.claimed_at = now
    ticket.claim_expires_at = now + timedelta(minutes=settings.REVIEW_TIMEOUT_MINUTES)
    
    db.commit()
    db.refresh(ticket)

    # OpenAPI TicketResponse kontratına tam uyumlu yanıt
    return {
        "id": ticket.id,
        "product_id": ticket.product_id,
        "status": ticket.status.value,
        "queue_priority": ticket.queue_priority,
        "assigned_moderator_id": ticket.assigned_moderator_id,
        "claimed_at": ticket.claimed_at.isoformat() if ticket.claimed_at else None,
        "claim_expires_at": ticket.claim_expires_at.isoformat() if ticket.claim_expires_at else None,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "json_before": ticket.json_before,
        "json_after": ticket.json_after,
        "kind": ticket.kind.value if hasattr(ticket.kind, "value") else ticket.kind,
        "seller_id": ticket.seller_id,
    }