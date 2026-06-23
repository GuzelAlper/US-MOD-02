from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Межсервисная авторизация
    SERVICE_KEY: str = "moderation-service-key-change-in-production"
    
    # База данных
    DATABASE_URL: str = "sqlite:///./moderation.db"
    
    # Таймаут удержания карточки в модерации
    REVIEW_TIMEOUT_MINUTES: int = 30
    
    # Опциональные настройки
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()