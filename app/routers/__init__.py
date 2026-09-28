from app.routers.users import router as users_router
from app.routers.movies import router as movies_router
from app.routers.genres import router as genres_router
from app.routers.recommendations import router as recommendations_router
from app.routers.cache import router as cache_router
from app.routers.health import router as health_router

__all__ = [
    "users_router",
    "movies_router",
    "genres_router",
    "recommendations_router",
    "cache_router",
    "health_router",
]
