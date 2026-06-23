from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.product_card import ProductCard
from app.core.config import settings

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
headers = {'X-Service-Key': settings.SERVICE_KEY}
payload = {
    'event_type': 'PRODUCT_CREATED',
    'product_id': 'prod_001',
    'idempotency_key': 'idem_001',
    'seller_id': 'seller_001',
    'occurred_at': '2026-06-18T12:00:00Z',
    'payload': {
        'name': 'Test Product',
        'description': 'Desc',
        'price': 99.9,
        'category': 'elec'
    }
}
resp = client.post('/api/v1/b2b/events', json=payload, headers=headers)
print('resp', resp.status_code, resp.text)

db = TestingSessionLocal()
card = db.query(ProductCard).filter(ProductCard.product_id == 'prod_001').first()
print('card', card)
print('count', db.query(ProductCard).count())
db.close()
