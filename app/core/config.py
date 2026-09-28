import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "StreamRec - Plataforma de Recomendação"
    DESCRIPTION: str = "API de recomendação personalizada de filmes utilizando Neo4j (grafo) e Redis (cache TTL)"
    VERSION: str = "1.0.0"
    
    # Neo4j Settings
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password123"
    NEO4J_DATABASE: str = "neo4j"
    
    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_CACHE_TTL: int = 60  # Cache TTL in seconds
    
    # Fallback mode for demonstration/evaluation if services are not immediately running locally
    USE_MOCK_FALLBACK: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
