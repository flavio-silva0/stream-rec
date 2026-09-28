import json
import time
import logging
from typing import Optional, List, Dict, Any, Tuple
from app.database.redis_client import redis_client
from app.repositories.recommendation_repo import recommendation_repo
from app.repositories.user_repo import user_repo
from app.models.schemas import RecommendationResponse, RecommendationItem
from app.core.config import settings

logger = logging.getLogger("streamrec.service")

class RecommendationService:
    def _build_cache_key(self, user_id: str, strategy: str, limit: int) -> str:
        """Padrão de chave de cache por usuário, estratégia e limite."""
        return f"rec:user:{user_id}:{strategy}:limit:{limit}"

    async def get_recommendations(
        self,
        user_id: str,
        strategy: str = "hybrid",
        limit: int = 5,
        bypass_cache: bool = False
    ) -> Tuple[RecommendationResponse, str]:
        """
        Retorna recomendações personalizadas com estratégia Cache-Aside:
        1. Consulta o Redis pela chave rec:user:{user_id}:{strategy}:limit:{limit}
        2. Se HIT: retorna os dados em memória cache com latência mínima e TTL restante.
        3. Se MISS: executa a consulta de grafos no Neo4j, armazena o resultado no Redis com TTL e retorna.
        
        Retorna (RecommendationResponse, cache_header) onde cache_header é 'HIT' ou 'MISS'.
        """
        start_time = time.perf_counter()
        cache_key = self._build_cache_key(user_id, strategy, limit)
        user = await user_repo.get_user_by_id(user_id)
        user_name = user.name if user else None

        # 1. Tenta recuperar do Cache Redis (se não estiver em bypass)
        if not bypass_cache and redis_client.is_connected:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                redis_client.record_hit()
                remaining_ttl = await redis_client.ttl(cache_key)
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
                
                try:
                    items_raw = json.loads(cached_data)
                    items = [RecommendationItem(**item) for item in items_raw]
                    
                    logger.info(" CACHE HIT para usuário '%s' [chave: %s, TTL: %ds, tempo: %.2fms]",
                                user_id, cache_key, remaining_ttl, elapsed_ms)
                    
                    resp = RecommendationResponse(
                        user_id=user_id,
                        user_name=user_name,
                        strategy=strategy,
                        cache_status="CACHE HIT",
                        ttl_remaining_seconds=remaining_ttl if remaining_ttl >= 0 else None,
                        response_time_ms=elapsed_ms,
                        total_results=len(items),
                        data=items
                    )
                    return resp, "HIT"
                except Exception as e:
                    logger.error("Erro ao desserializar cache de '%s': %s", cache_key, e)

        # 2. CACHE MISS: consulta o banco de grafos Neo4j
        redis_client.record_miss()
        logger.info(" CACHE MISS para usuário '%s' [chave: %s]. Consultando grafo Neo4j...", user_id, cache_key)

        strat_lower = strategy.lower()
        if strat_lower == "collaborative":
            items = await recommendation_repo.get_user_collaborative_recommendations(user_id, limit=limit)
        elif strat_lower == "genre":
            items = await recommendation_repo.get_user_genre_recommendations(user_id, limit=limit)
        elif strat_lower == "trending":
            items = await recommendation_repo.get_trending_recommendations(user_id, limit=limit)
        else:
            items = await recommendation_repo.get_hybrid_recommendations(user_id, limit=limit)

        # 3. Grava no Redis com TTL configurado
        if redis_client.is_connected:
            try:
                serialized = json.dumps([item.model_dump() for item in items])
                await redis_client.set(cache_key, serialized, ex=settings.REDIS_CACHE_TTL)
                logger.info(" Gravado no Redis cache com TTL de %ds: %s", settings.REDIS_CACHE_TTL, cache_key)
            except Exception as e:
                logger.error("Erro ao salvar no Redis cache: %s", e)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        resp = RecommendationResponse(
            user_id=user_id,
            user_name=user_name,
            strategy=strategy,
            cache_status="CACHE MISS",
            ttl_remaining_seconds=settings.REDIS_CACHE_TTL,
            response_time_ms=elapsed_ms,
            total_results=len(items),
            data=items
        )
        return resp, "MISS"

    async def invalidate_user_cache(self, user_id: str) -> int:
        """
        Invalida todas as chaves de recomendações em cache do usuário.
        Padrão: rec:user:{user_id}:*
        """
        pattern = f"rec:user:{user_id}:*"
        removed = await redis_client.delete_pattern(pattern)
        logger.info(" Cache invalidado para o usuário '%s'. %d chave(s) removida(s).", user_id, removed)
        return removed

    async def clear_all_cache(self) -> int:
        """Limpa todo o cache de recomendações da aplicação."""
        removed = await redis_client.clear_all("rec:*")
        logger.info(" Todo o cache de recomendações foi limpo. %d chave(s) removida(s).", removed)
        return removed

recommendation_service = RecommendationService()
