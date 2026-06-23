from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.models.product_card import ProductCard

engine = create_engine(
    'sqlite://',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    result = conn.execute(text("PRAGMA table_info(product_cards)"))
    print('schema:')
    for row in result:
        print(tuple(row))
    print('columns', [row[1] for row in conn.execute(text("PRAGMA table_info(product_cards)"))])
    # insert a dummy row to verify columns exist
    session = SessionLocal()
    card = ProductCard(id='c1', product_id='p1', status=ProductCard.status.type.enum_class.PENDING, queue_priority=2)
    session.add(card)
    session.commit()
    print('inserted')
    session.close()
