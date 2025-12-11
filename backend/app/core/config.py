"""
Configuración centralizada de la aplicación.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Configuración global usando Pydantic Settings"""
    
    # Entorno
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # APIs externas - TinRed
    TINRED_API_URL: str = "https://test.tinred.pe"
    TINRED_API_KEY: Optional[str] = None
    TINRED_IDENTIFY_URL: str = "https://test.tinred.pe/SisFact/api/identify_ai"
    TINRED_STORE_URL: str = "https://test.tinred.pe/SisFact/api/store_agente_api"
    TINRED_STORE_AGENTE_URL: Optional[str] = None
    TINRED_CLIENT_LIST_URL: str = "https://test.tinred.pe/SisFact/api/client_agente_ai"
    TINRED_PRODUCT_LIST_URL: str = "https://test.tinred.pe/SisFact/api/product_agente_ai"
    TINRED_HISTORY_URL: str = "https://test.tinred.pe/SisFact/api/record_agente_ai"
    TINRED_VERIFY_SSL: bool = False
    TINRED_TIMEOUT: int = 60
    
    # Legacy URLs
    INVOICE_API_URL: Optional[str] = None
    
    # IA - Google Gemini
    GOOGLE_API_KEY: str = ""
    MODEL_NAME: str = "gemini-2.0-flash-exp"
    EMBEDDING_MODEL: str = "models/text-embedding-004"
    
    # Servidor
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BACKEND_URL: str = "http://localhost:8000"
    API_KEY: Optional[str] = None
    
    # Cache y Memoria
    SESSION_TTL_HOURS: int = 24
    CONTEXT_CACHE_TTL_MINUTES: int = 60
    MAX_CONVERSATION_HISTORY: int = 20
    
    # Límites
    MAX_MESSAGE_LENGTH: int = 5000
    MAX_ITEMS_PER_INVOICE: int = 50
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
