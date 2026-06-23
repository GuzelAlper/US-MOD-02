from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.product_card import ProductCard, CardStatus
from datetime import datetime

SQLALCHEMY_DATABASE_URL = 'sqlite://'
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={'check_same_thread': False},
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

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

# Insert two test cards
with TestingSessionLocal() as db:
    older_card = ProductCard(
        id='card_old', product_id='prod_old', status=CardStatus.PENDING,
        queue_priority=2, created_at=datetime.fromisoformat('2026-06-18T10:00:00')
    )
    newer_card = ProductCard(
        id='card_new', product_id='prod_new', status=CardStatus.PENDING,
        queue_priority=2, created_at=datetime.fromisoformat('2026-06-18T11:00:00')
    )
    db.add_all([older_card, newer_card])
    db.commit()

resp = client.post('/api/v1/queue/claim', json={'moderator_id': 'mod_1'})
print('response', resp.status_code, resp.text)
with TestingSessionLocal() as db:
    card = db.query(ProductCard).filter(ProductCard.product_id == 'prod_old').one_or_none()
    print('card after', card, card.status if card else None, card.assigned_moderator_id if card else None)
