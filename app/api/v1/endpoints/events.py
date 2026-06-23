from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.event import ProductEvent
from app.services.product_service import ProductService
from app.core.config import settings

# Prefix'i burada değil main.py'de tanımladığımız için burası temiz kalıyor
router = APIRouter()

@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def receive_product_event(
    event: ProductEvent,
    db: Session = Depends(get_db),
    x_service_key: str = Header(None, alias="X-Service-Key")
):
    """
    B2B servisinden gelen ürün etkinliklerini işler.
    Dokümantasyon uyumu: POST /api/v1/b2b/events
    """
    
    # 1. Yetkilendirme Kontrolü
    if not x_service_key or x_service_key != settings.SERVICE_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Missing or invalid X-Service-Key header"
            }
        )
    
    # 2. Servis Çağrısı (Service layer içinde 409 hatasını fırlatacağız)
    service = ProductService(db)
    processed = service.process_event(event)

    # 3. Eğer event duplicate ise yan etki yok -> 200
    if not processed:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "duplicate"})

    # 4. Başarılı işleme -> 202
    return {"status": "accepted"}