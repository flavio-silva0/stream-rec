from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

# ==================== User Models ====================
class UserBase(BaseModel):
    name: str = Field(..., examples=["Alice Silva"])
    email: EmailStr = Field(..., examples=["alice.silva@exemplo.com"])

class UserCreate(UserBase):
    id: Optional[str] = Field(None, examples=["user-alice"], description="ID único. Se omitido, será gerado automaticamente.")

class UserResponse(UserBase):
    id: str
    created_at: Optional[str] = None
    watched_count: int = 0
    ratings_count: int = 0

class UserWatchedItem(BaseModel):
    movie_id: str
    title: str
    release_year: Optional[int] = None
    genres: List[str] = []
    watched_at: Optional[str] = None

class UserRatingItem(BaseModel):
    movie_id: str
    title: str
    rating: float
    comment: Optional[str] = None
    rated_at: Optional[str] = None

class UserDetailResponse(UserResponse):
    watched_movies: List[UserWatchedItem] = []
    ratings: List[UserRatingItem] = []

# ==================== Genre Models ====================
class GenreCreate(BaseModel):
    name: str = Field(..., examples=["Ficção Científica"], description="Nome único do gênero")

class GenreResponse(BaseModel):
    name: str
    movie_count: Optional[int] = 0

# ==================== Movie Models ====================
class MovieBase(BaseModel):
    title: str = Field(..., examples=["A Origem (Inception)"])
    release_year: int = Field(..., ge=1888, le=2100, examples=[2010])
    genres: List[str] = Field(default_factory=list, examples=[["Ficção Científica", "Ação", "Suspense"]])

class MovieCreate(MovieBase):
    id: Optional[str] = Field(None, examples=["movie-inception"], description="ID único. Se omitido, será gerado a partir do título.")

class MovieResponse(MovieBase):
    id: str
    avg_rating: Optional[float] = None
    rating_count: int = 0

# ==================== Interaction Models ====================
class WatchedCreate(BaseModel):
    movie_id: str = Field(..., examples=["movie-inception"])
    watched_at: Optional[str] = Field(None, examples=["2026-09-28T18:00:00Z"])

class WatchedResponse(BaseModel):
    user_id: str
    movie_id: str
    movie_title: Optional[str] = None
    watched_at: str
    cache_invalidated: bool = True

class RatingCreate(BaseModel):
    movie_id: str = Field(..., examples=["movie-inception"])
    rating: float = Field(..., ge=1.0, le=5.0, examples=[5.0], description="Nota de 1.0 a 5.0")
    comment: Optional[str] = Field(None, examples=["Excelente filme, roteiro surpreendente!"])
    rated_at: Optional[str] = Field(None, examples=["2026-09-28T18:05:00Z"])

class RatingResponse(BaseModel):
    user_id: str
    movie_id: str
    movie_title: Optional[str] = None
    rating: float
    comment: Optional[str] = None
    rated_at: str
    cache_invalidated: bool = True

# ==================== Recommendation Models ====================
class RecommendationItem(BaseModel):
    movie_id: str
    title: str
    release_year: Optional[int] = None
    genres: List[str] = []
    predicted_rating: float
    score: float
    reason: str

class RecommendationResponse(BaseModel):
    user_id: str
    user_name: Optional[str] = None
    strategy: str
    cache_status: str = Field(..., examples=["CACHE HIT"], description="CACHE HIT ou CACHE MISS")
    ttl_remaining_seconds: Optional[int] = Field(None, description="Segundos restantes no TTL do Redis")
    response_time_ms: float = Field(..., description="Tempo de resposta em milissegundos")
    total_results: int
    data: List[RecommendationItem]

# ==================== Cache Models ====================
class CacheStatsResponse(BaseModel):
    is_connected: bool
    backend: str
    keys_count: int
    hit_count: int
    miss_count: int
    hit_rate_pct: float
    default_ttl_seconds: int

class CacheInvalidateResponse(BaseModel):
    message: str
    keys_removed: int
    user_id: Optional[str] = None

# ==================== Health & Seed Models ====================
class HealthResponse(BaseModel):
    status: str
    neo4j: dict
    redis: dict
    version: str

class SeedResponse(BaseModel):
    message: str
    users_created: int
    genres_created: int
    movies_created: int
    watched_created: int
    ratings_created: int
