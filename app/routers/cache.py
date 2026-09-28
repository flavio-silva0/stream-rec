from fastapi import APIRouter, Path
from app.database.redis_client import redis_client
from app.services.recommendation_service import recommendation_service
from app.models.schemas import CacheStatsResponse, CacheInvalidateResponse

router = APIRouter(prefix="/cache", tags=["Cache Redis"])

@router.get("/stats", response_model=CacheStatsResponse, summary="Estatísticas do Cache Redis")
async def get_cache_stats():
    """
    Retorna métricas em tempo real de CACHE HIT, CACHE MISS, taxa de acerto (%) e total de chaves ativas.
    """
    stats = await redis_client.get_stats()
    return CacheStatsResponse(**stats)

@router.delete("/user/{user_id}", response_model=CacheInvalidateResponse, summary="Invalidar cache de um usuário")
async def invalidate_user_cache(
    user_id: str = Path(..., examples=["user-carlos"], description="ID do usuário para purgar o cache de recomendações")
):
    """
    Remove manualmente todas as recomendações armazenadas em cache para o usuário especificado.
    """
    removed = await recommendation_service.invalidate_user_cache(user_id)
    return CacheInvalidateResponse(
        message=f"Cache do usuário '{user_id}' invalidado com sucesso.",
        keys_removed=removed,
        user_id=user_id
    )

@router.delete("/all", response_model=CacheInvalidateResponse, summary="Limpar todo o cache de recomendações")
async def clear_all_cache():
    """
    Remove todas as chaves de recomendações ativas no Redis (`rec:*`).
    """
    removed = await recommendation_service.clear_all_cache()
    return CacheInvalidateResponse(
        message="Todo o cache de recomendações foi limpo com sucesso.",
        keys_removed=removed,
        user_id=None
    )
