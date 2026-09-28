import logging
import asyncio
from typing import Optional, Dict, Any, List
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger("streamrec.redis")

class RedisClient:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self.is_connected: bool = False
        self.mode: str = "uninitialized"
        self.hit_count: int = 0
        self.miss_count: int = 0

    async def connect(self):
        try:
            client = aioredis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_timeout=1.5,
                socket_connect_timeout=1.5
            )
            await asyncio.wait_for(client.ping(), timeout=1.5)
            self._redis = client
            self.is_connected = True
            self.mode = "redis_live"
            logger.info(" Conexão com Redis estabelecida com sucesso em %s:%d", settings.REDIS_HOST, settings.REDIS_PORT)
        except Exception as e:
            self.is_connected = False
            if settings.USE_MOCK_FALLBACK:
                try:
                    import fakeredis.aioredis
                    self._redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
                    self.is_connected = True
                    self.mode = "fakeredis_fallback"
                    logger.warning(
                        " Redis não disponível em %s:%d (%s). Utilizando fakeredis (in-memory) com suporte a TTL e chaves.",
                        settings.REDIS_HOST, settings.REDIS_PORT, str(e)
                    )
                except Exception as fe:
                    logger.error(" Erro ao inicializar fakeredis: %s", str(fe))
            else:
                logger.error(" Falha ao conectar ao Redis: %s", str(e))
                raise

    async def close(self):
        if self._redis:
            await self._redis.aclose()
            self.is_connected = False
            logger.info("Conexão com Redis encerrada.")

    def record_hit(self):
        self.hit_count += 1

    def record_miss(self):
        self.miss_count += 1

    async def get(self, key: str) -> Optional[str]:
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.error("Erro no Redis GET '%s': %s", key, e)
            return None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        if not self._redis:
            return False
        try:
            ttl_to_use = ex if ex is not None else settings.REDIS_CACHE_TTL
            await self._redis.set(key, value, ex=ttl_to_use)
            return True
        except Exception as e:
            logger.error("Erro no Redis SET '%s': %s", key, e)
            return False

    async def ttl(self, key: str) -> int:
        if not self._redis:
            return -2
        try:
            return await self._redis.ttl(key)
        except Exception as e:
            logger.error("Erro no Redis TTL '%s': %s", key, e)
            return -2

    async def delete(self, key: str) -> int:
        if not self._redis:
            return 0
        try:
            return await self._redis.delete(key)
        except Exception as e:
            logger.error("Erro no Redis DEL '%s': %s", key, e)
            return 0

    async def delete_pattern(self, pattern: str) -> int:
        """Remove todas as chaves correspondentes a um padrão (ex: rec:user-1:*)."""
        if not self._redis:
            return 0
        try:
            keys: List[str] = await self._redis.keys(pattern)
            if keys:
                return await self._redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error("Erro no Redis delete_pattern '%s': %s", pattern, e)
            return 0

    async def clear_all(self, prefix: str = "rec:*") -> int:
        """Limpa chaves com determinado prefixo de cache."""
        return await self.delete_pattern(prefix)

    async def count_keys(self, pattern: str = "rec:*") -> int:
        if not self._redis:
            return 0
        try:
            keys = await self._redis.keys(pattern)
            return len(keys)
        except Exception as e:
            logger.error("Erro no Redis keys count: %s", e)
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0.0
        keys_count = await self.count_keys("rec:*")
        return {
            "is_connected": self.is_connected,
            "backend": self.mode,
            "keys_count": keys_count,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate_pct": round(hit_rate, 2),
            "default_ttl_seconds": settings.REDIS_CACHE_TTL
        }

    async def health_check(self) -> Dict[str, Any]:
        if not self.is_connected or not self._redis:
            return {"status": "disconnected"}
        try:
            await self._redis.ping()
            return {
                "status": "healthy",
                "backend": self.mode,
                "host": settings.REDIS_HOST if self.mode == "redis_live" else "in-memory (fakeredis)",
                "port": settings.REDIS_PORT if self.mode == "redis_live" else 0,
                "default_ttl_seconds": settings.REDIS_CACHE_TTL
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "backend": self.mode}

redis_client = RedisClient()
