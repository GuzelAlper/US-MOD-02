import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.product_card import ProductCard, CardStatus, IdempotencyKey

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

@pytest.fixture(autouse=True)
def clear_db():
    db = TestingSessionLocal()
    db.query(ProductCard).delete()
    db.query(IdempotencyKey).delete()
    db.commit()
    db.close()


def test_next_returns_oldest_pending(client):
    db = TestingSessionLocal()
    older_card = ProductCard(
        id="card_old", product_id="prod_old", status=CardStatus.PENDING,
        queue_priority=2, created_at=datetime.fromisoformat("2026-06-18T10:00:00")
    )
    newer_card = ProductCard(
        id="card_new", product_id="prod_new", status=CardStatus.PENDING,
        queue_priority=2, created_at=datetime.fromisoformat("2026-06-18T11:00:00")
    )
    db.add_all([older_card, newer_card])
    db.commit()
    db.close()

    response = client.post("/api/v1/queue/claim", json={"moderator_id": "mod_1"})
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == "prod_old"
    assert data["status"] == "IN_REVIEW"
    assert data["assigned_moderator_id"] == "mod_1"

    db = TestingSessionLocal()
    card = db.query(ProductCard).filter(ProductCard.product_id == "prod_old").one()
    assert card.status == CardStatus.IN_REVIEW
    assert card.assigned_moderator_id == "mod_1"
    db.close()


def test_empty_queue_returns_204(client):
    response = client.post("/api/v1/queue/claim", json={"moderator_id": "mod_2"})
    assert response.status_code == 204


def test_moderator_already_has_in_review_returns_409(client):
    db = TestingSessionLocal()
    existing = ProductCard(
        id="card_existing", product_id="prod_existing", status=CardStatus.IN_REVIEW,
        assigned_moderator_id="mod_3", queue_priority=1,
        created_at=datetime.fromisoformat("2026-06-18T10:00:00")
    )
    db.add(existing)
    db.commit()
    db.close()

    response = client.post("/api/v1/queue/claim", json={"moderator_id": "mod_3"})
    assert response.status_code == 409
    assert response.json() == {
        "code": "MODERATOR_ALREADY_HAS_ACTIVE_REVIEW",
        "message": "Moderator already has an active IN_REVIEW ticket."
    }


def test_concurrent_two_moderators_get_different_cards(client):
    db = TestingSessionLocal()
    card1 = ProductCard(
        id="card_a", product_id="prod_a", status=CardStatus.PENDING, queue_priority=1,
        created_at=datetime.fromisoformat("2026-06-18T10:00:00")
    )
    card2 = ProductCard(
        id="card_b", product_id="prod_b", status=CardStatus.PENDING, queue_priority=1,
        created_at=datetime.fromisoformat("2026-06-18T10:05:00")
    )
    db.add_all([card1, card2])
    db.commit()
    db.close()

    response1 = client.post("/api/v1/queue/claim", json={"moderator_id": "mod_a"})
    response2 = client.post("/api/v1/queue/claim", json={"moderator_id": "mod_b"})

    assert response1.status_code == 200
    assert response2.status_code == 200
    assert response1.json()["product_id"] != response2.json()["product_id"]
    assert {response1.json()["product_id"], response2.json()["product_id"]} == {"prod_a", "prod_b"}
