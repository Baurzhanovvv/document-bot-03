

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TOKEN: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    DB_URL: str
    OPENSEARCH_HOST: str
    OPENSEARCH_PORT: int
    OPENSEARCH_USER: str
    OPENSEARCH_PASSWORD: str
    OPENSEARCH_SSL: bool
    OPENSEARCH_VERIFY: bool
    TIKA_URL: str
    UPLOAD_DIR: str
    SYNONYMS_DIR: str
    OPENSEARCH_SCHEME: str
    OPENSEARCH_INDEX: str
    PAGE_SIZE: int
    WEBAPP_URL: str
    PAYMENT_SUCCESS_URL: Optional[str] = None
    OPENSEARCH_SCHEME: str
    OPENSEARCH_INDEX: str
    
    # Настройки ЮKassa
    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    SUBSCRIPTION_PRICE: float = 299.0  # Цена подписки по умолчанию
    YOOKASSA_TEST_MODE: bool = True  # True для тестового режима, False для боевого

    class Config:
        env_file = '.env'


settings = Settings()
