import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.product_card import ProductCard, CardStatus, IdempotencyKey
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def client():
    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client_app:
        yield client_app
    if original is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = original

HEADERS = {"X-Service-Key": settings.SERVICE_KEY}

@pytest.fixture(autouse=True)
def clear_db():
    db = TestingSessionLocal()
    db.query(ProductCard).delete()
    db.query(IdempotencyKey).delete()
    db.commit()
    db.close()

def test_created_pending(client):
    payload = {
        "event_type": "PRODUCT_CREATED",
        "product_id": "prod_001",
        "idempotency_key": "idem_001",
        "seller_id": "seller_001",
        "occurred_at": "2026-06-18T12:00:00Z",
        "payload": {"name": "Test Product", "description": "Desc", "price": 99.9, "category": "elec"}
    }
    response = client.post("/api/v1/b2b/events", json=payload, headers=HEADERS)
    assert response.status_code == 202
    
    db = TestingSessionLocal()
    card = db.query(ProductCard).filter(ProductCard.product_id == "prod_001").first()
    assert card is not None
    assert card.status == CardStatus.PENDING
    db.close()

def test_edited_returns_to_review(client):
    db = TestingSessionLocal()
    card = ProductCard(id="card_001", product_id="prod_002", status=CardStatus.APPROVED)
    db.add(card)
    db.commit()
    db.close()
    
    payload = {
        "event_type": "PRODUCT_EDITED",
        "product_id": "prod_002",
        "idempotency_key": "idem_002",
        "occurred_at": "2026-06-18T12:00:00Z",
        "payload": {"json_after": {"name": "New Name"}}
    }
    
    response = client.post("/api/v1/b2b/events", json=payload, headers=HEADERS)
    assert response.status_code == 202
    
    db = TestingSessionLocal()
    card = db.query(ProductCard).filter(ProductCard.product_id == "prod_002").first()
    assert card.status == CardStatus.PENDING
    assert card.name == "New Name"
    db.close()

def test_duplicate_event_409(client):
    payload = {
        "event_type": "PRODUCT_CREATED",
        "product_id": "prod_005",
        "idempotency_key": "idem_005",
        "occurred_at": "2026-06-18T12:00:00Z",
        "payload": {"json_after": {"name": "Product"}}
    }
    
    # İlk istek
    response1 = client.post("/api/v1/b2b/events", json=payload, headers=HEADERS)
    assert response1.status_code == 202

    # İkinci istek (Duplicate) -> should be 200 with no side effects
    response2 = client.post("/api/v1/b2b/events", json=payload, headers=HEADERS)
    assert response2.status_code == 200
    assert response2.json()["status"] == "duplicate"

    # Ensure only one card exists for the product
    db = TestingSessionLocal()
    cards = db.query(ProductCard).filter(ProductCard.product_id == "prod_005").all()
    assert len(cards) == 1
    db.close()

def test_edited_updates_in_review(client):
    db = TestingSessionLocal()
    card = ProductCard(id="card_003", product_id="prod_003", status=CardStatus.IN_REVIEW, name="Old")
    db.add(card)
    db.commit()
    db.close()

    payload = {
        "event_type": "PRODUCT_EDITED",
        "product_id": "prod_003",
        "idempotency_key": "idem_003",
        "occurred_at": "2026-06-18T12:00:00Z",
        "payload": {"json_after": {"name": "Updated"}}
    }

    response = client.post("/api/v1/b2b/events", json=payload, headers=HEADERS)
    assert response.status_code == 202

    db = TestingSessionLocal()
    card = db.query(ProductCard).filter(ProductCard.product_id == "prod_003").first()
    assert card.status == CardStatus.IN_REVIEW
    assert card.name == "Updated"
    db.close()

def test_missing_service_header_401(client):
    payload = {
        "event_type": "PRODUCT_CREATED",
        "product_id": "prod_006",
        "idempotency_key": "idem_006",
        "occurred_at": "2026-06-18T12:00:00Z",
        "payload": {"json_after": {"name": "Test"}}
    }
    
    response = client.post("/api/v1/b2b/events", json=payload)
    assert response.status_code == 401