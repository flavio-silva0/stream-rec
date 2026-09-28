from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr

# ==================== User Models ====================
class UserBase(BaseModel):
    name: str = Field(..., examples=["Alice Silva"], description="Nome completo do usuário")
    email: EmailStr = Field(..., examples=["alice.silva@exemplo.com"], description="E-mail único do usuário")

class UserCreate(UserBase):
    id: Optional[str] = Field(None, examples=["user-alice"], description="ID único. Se omitido, será gerado automaticamente.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "user-alice",
                "name": "Alice Silva",
                "email": "alice.silva@streamrec.com"
            }
        }
    }

class UserResponse(UserBase):
    id: str = Field(..., examples=["user-alice"])
    created_at: Optional[str] = Field(None, examples=["2026-09-28T18:00:00Z"])
    watched_count: int = Field(0, examples=[3])
    ratings_count: int = Field(0, examples=[2])

class UserWatchedItem(BaseModel):
    movie_id: str = Field(..., examples=["mov-inception"])
    title: str = Field(..., examples=["A Origem (Inception)"])
    release_year: Optional[int] = Field(None, examples=[2010])
    genres: List[str] = Field(default_factory=list, examples=[["Ficção Científica", "Ação"]])
    watched_at: Optional[str] = Field(None, examples=["2026-09-28T18:00:00Z"])

class UserRatingItem(BaseModel):
    movie_id: str = Field(..., examples=["mov-inception"])
    title: str = Field(..., examples=["A Origem (Inception)"])
    rating: float = Field(..., examples=[5.0])
    comment: Optional[str] = Field(None, examples=["Obra-prima do cinema contemporâneo!"])
    rated_at: Optional[str] = Field(None, examples=["2026-09-28T18:05:00Z"])

class UserDetailResponse(UserResponse):
    watched_movies: List[UserWatchedItem] = []
    ratings: List[UserRatingItem] = []

# ==================== Genre Models ====================
class GenreCreate(BaseModel):
    name: str = Field(..., examples=["Ficção Científica"], description="Nome único do gênero")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Ficção Científica"
            }
        }
    }

class GenreResponse(BaseModel):
    name: str = Field(..., examples=["Ficção Científica"])
    movie_count: Optional[int] = Field(0, examples=[5])

# ==================== Movie Models ====================
class MovieBase(BaseModel):
    title: str = Field(..., examples=["A Origem (Inception)"], description="Título do filme")
    release_year: int = Field(..., ge=1888, le=2100, examples=[2010], description="Ano de lançamento")
    genres: List[str] = Field(
        default_factory=list,
        examples=[["Ficção Científica", "Ação", "Suspense"]],
        description="Lista de gêneros vinculados ao filme"
    )

class MovieCreate(MovieBase):
    id: Optional[str] = Field(None, examples=["mov-inception"], description="ID único. Se omitido, será gerado a partir do título.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "mov-inception",
                "title": "A Origem (Inception)",
                "release_year": 2010,
                "genres": ["Ficção Científica", "Ação", "Suspense"]
            }
        }
    }

class MovieResponse(MovieBase):
    id: str = Field(..., examples=["mov-inception"])
    avg_rating: Optional[float] = Field(None, examples=[4.8])
    rating_count: int = Field(0, examples=[15])

# ==================== Interaction Models ====================
class WatchedCreate(BaseModel):
    movie_id: str = Field(..., examples=["mov-inception"], description="ID do filme assistido")
    watched_at: Optional[str] = Field(None, examples=["2026-09-28T18:00:00Z"], description="Data/hora ISO opcional")

    model_config = {
        "json_schema_extra": {
            "example": {
                "movie_id": "mov-matrix",
                "watched_at": "2026-09-28T18:00:00Z"
            }
        }
    }

class WatchedResponse(BaseModel):
    user_id: str = Field(..., examples=["user-carlos"])
    movie_id: str = Field(..., examples=["mov-matrix"])
    movie_title: Optional[str] = Field(None, examples=["Matrix"])
    watched_at: str = Field(..., examples=["2026-09-28T18:00:00Z"])
    cache_invalidated: bool = Field(True, description="Indica se o cache do usuário foi invalidado")

class RatingCreate(BaseModel):
    movie_id: str = Field(..., examples=["mov-inception"], description="ID do filme a ser avaliado")
    rating: float = Field(..., ge=1.0, le=5.0, examples=[5.0], description="Nota de 1.0 a 5.0")
    comment: Optional[str] = Field(None, examples=["Excelente filme, roteiro surpreendente!"], description="Comentário opcional")
    rated_at: Optional[str] = Field(None, examples=["2026-09-28T18:05:00Z"], description="Data/hora ISO opcional")

    model_config = {
        "json_schema_extra": {
            "example": {
                "movie_id": "mov-blade-runner",
                "rating": 5.0,
                "comment": "Visual e narrativa impecáveis!"
            }
        }
    }

class RatingResponse(BaseModel):
    user_id: str = Field(..., examples=["user-carlos"])
    movie_id: str = Field(..., examples=["mov-blade-runner"])
    movie_title: Optional[str] = Field(None, examples=["Blade Runner 2049"])
    rating: float = Field(..., examples=[5.0])
    comment: Optional[str] = Field(None, examples=["Visual e narrativa impecáveis!"])
    rated_at: str = Field(..., examples=["2026-09-28T18:05:00Z"])
    cache_invalidated: bool = Field(True, description="Indica se o cache do usuário foi invalidado")

# ==================== Recommendation Models ====================
class RecommendationItem(BaseModel):
    movie_id: str = Field(..., examples=["mov-blade-runner"])
    title: str = Field(..., examples=["Blade Runner 2049"])
    release_year: Optional[int] = Field(None, examples=[2017])
    genres: List[str] = Field(default_factory=list, examples=[["Ficção Científica", "Drama", "Suspense"]])
    predicted_rating: float = Field(..., examples=[4.9])
    score: float = Field(..., examples=[3.34])
    reason: str = Field(..., examples=["Recomendado com base nas avaliações de 1 usuário(s) com gostos afins"])

class RecommendationResponse(BaseModel):
    user_id: str = Field(..., examples=["user-carlos"])
    user_name: Optional[str] = Field(None, examples=["Carlos SciFi"])
    strategy: str = Field(..., examples=["hybrid"])
    cache_status: str = Field(..., examples=["CACHE HIT"], description="Identifica se veio do cache (CACHE HIT) ou do grafo (CACHE MISS)")
    ttl_remaining_seconds: Optional[int] = Field(None, examples=[58], description="Segundos restantes no TTL do Redis")
    response_time_ms: float = Field(..., examples=[0.48], description="Tempo de resposta em milissegundos")
    total_results: int = Field(..., examples=[4])
    data: List[RecommendationItem]

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user-carlos",
                "user_name": "Carlos SciFi",
                "strategy": "hybrid",
                "cache_status": "CACHE HIT",
                "ttl_remaining_seconds": 58,
                "response_time_ms": 0.48,
                "total_results": 2,
                "data": [
                    {
                        "movie_id": "mov-blade-runner",
                        "title": "Blade Runner 2049",
                        "release_year": 2017,
                        "genres": ["Ficção Científica", "Drama", "Suspense"],
                        "predicted_rating": 4.9,
                        "score": 3.34,
                        "reason": "Recomendado com base nas avaliações de 1 usuário(s) com gostos afins"
                    },
                    {
                        "movie_id": "mov-dark-knight",
                        "title": "Batman: O Cavaleiro das Trevas",
                        "release_year": 2008,
                        "genres": ["Ação", "Crime", "Drama"],
                        "predicted_rating": 4.8,
                        "score": 3.28,
                        "reason": "Recomendado com base nas avaliações de 1 usuário(s) com gostos afins"
                    }
                ]
            }
        }
    }

# ==================== Cache Models ====================
class CacheStatsResponse(BaseModel):
    is_connected: bool = Field(True, examples=[True])
    backend: str = Field(..., examples=["fakeredis_fallback", "redis_live"])
    keys_count: int = Field(..., examples=[4])
    hit_count: int = Field(..., examples=[12])
    miss_count: int = Field(..., examples=[4])
    hit_rate_pct: float = Field(..., examples=[75.0])
    default_ttl_seconds: int = Field(60, examples=[60])

class CacheInvalidateResponse(BaseModel):
    message: str = Field(..., examples=["Cache do usuário 'user-carlos' invalidado com sucesso."])
    keys_removed: int = Field(..., examples=[2])
    user_id: Optional[str] = Field(None, examples=["user-carlos"])

# ==================== Health & Seed Models ====================
class Neo4jHealthStatus(BaseModel):
    status: str = Field(..., examples=["healthy", "fallback_active"])
    mode: str = Field(..., examples=["neo4j_live", "in_memory_fallback"])
    uri: Optional[str] = Field(None, examples=["bolt://localhost:7687"])
    database: Optional[str] = Field(None, examples=["neo4j"])
    users_count: Optional[int] = Field(None, examples=[4])
    movies_count: Optional[int] = Field(None, examples=[12])
    genres_count: Optional[int] = Field(None, examples=[8])
    note: Optional[str] = Field(None, examples=["Operando com grafo em memória"])

class RedisHealthStatus(BaseModel):
    status: str = Field(..., examples=["healthy"])
    backend: str = Field(..., examples=["redis_live", "fakeredis_fallback"])
    host: Optional[str] = Field(None, examples=["localhost", "in-memory (fakeredis)"])
    port: Optional[int] = Field(None, examples=[6379])
    default_ttl_seconds: int = Field(60, examples=[60])

class HealthResponse(BaseModel):
    status: str = Field(..., examples=["healthy"])
    neo4j: Neo4jHealthStatus
    redis: RedisHealthStatus
    version: str = Field(..., examples=["1.0.0"])

class SeedResponse(BaseModel):
    message: str = Field(..., examples=["Base de dados populada com sucesso!"])
    genres_created: int = Field(..., examples=[8])
    movies_created: int = Field(..., examples=[12])
    users_created: int = Field(..., examples=[4])
    watched_created: int = Field(..., examples=[13])
    ratings_created: int = Field(..., examples=[13])
