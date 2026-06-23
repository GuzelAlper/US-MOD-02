from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.product_card import ProductCard, IdempotencyKey, CardStatus
from app.schemas.event import ProductEvent
import uuid
import logging

logger = logging.getLogger(__name__)

class ProductService:
    def __init__(self, db: Session):
        self.db = db

    def process_event(self, event: ProductEvent) -> bool:
        # Return False if duplicate (no side effects), True if processed
        if self._is_duplicate(event.idempotency_key):
            return False

        if event.event_type == "PRODUCT_CREATED":
            self._handle_created(event)
        elif event.event_type == "PRODUCT_EDITED":
            self._handle_edited(event)
        elif event.event_type == "PRODUCT_DELETED":
            self._handle_deleted(event)

        self._save_idempotency_key(event.idempotency_key, event.product_id, event.event_type)
        return True

    def _handle_created(self, event: ProductEvent) -> None:
        p = event.payload
        card = ProductCard(
            id=str(uuid.uuid4()), product_id=event.product_id, seller_id=event.seller_id,
            name=p.name, description=p.description, price=p.price, category=p.category,
            queue_priority=p.queue_priority or 3,
            status=CardStatus.PENDING, json_after=p.model_dump()
        )
        self.db.add(card)
        self.db.commit()

    def _handle_edited(self, event: ProductEvent) -> None:
        p = event.payload
        card = self.db.query(ProductCard).filter(ProductCard.product_id == event.product_id).first()
        if not card: raise HTTPException(status_code=404, detail={"code": "PRODUCT_NOT_FOUND", "message": "Not found"})
        
        card.json_before = self._card_to_json(card)
        # Support both direct payload fields and nested `json_after` used in edit events
        if getattr(p, "json_after", None):
            after = p.json_after
            card.name = after.get("name") or card.name
            card.description = after.get("description") or card.description
            card.price = after.get("price") or card.price
            card.category = after.get("category") or card.category
            card.json_after = after
        else:
            card.name, card.description, card.price, card.category = (
                p.name or card.name,
                p.description or card.description,
                p.price or card.price,
                p.category or card.category,
            )
            card.json_after = p.model_dump()

        # If card currently IN_REVIEW, keep it IN_REVIEW (just update fields).
        # If it was APPROVED or BLOCKED, return it to PENDING for re-review.
        if card.status in [CardStatus.APPROVED, CardStatus.BLOCKED]:
            card.status = CardStatus.PENDING
        self.db.commit()

    # _handle_deleted, _is_duplicate, _save_idempotency_key, _card_to_json metodlarını eski halleriyle bırakabilirsin.

    def _handle_deleted(self, event: ProductEvent) -> None:
        card = self.db.query(ProductCard).filter(ProductCard.product_id == event.product_id).first()
        if card:
            card.json_before = self._card_to_json(card)
            card.status = CardStatus.ARCHIVED
            self.db.commit()

    def _card_to_json(self, card: ProductCard) -> dict:
        return {
            "product_id": card.product_id,
            "seller_id": card.seller_id,
            "name": card.name,
            "description": card.description,
            "price": card.price,
            "category": card.category,
            "status": card.status.value
        }

    def _is_duplicate(self, key: str) -> bool:
        if not key:
            return False
        return self.db.query(IdempotencyKey).filter(IdempotencyKey.key == key).first() is not None

    def _save_idempotency_key(self, key: str, product_id: str, event_type: str) -> None:
        if not key:
            return
        ik = IdempotencyKey(key=key, product_id=product_id, event_type=event_type)
        self.db.add(ik)
        self.db.commit()