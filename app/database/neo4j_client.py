import logging
import asyncio
from typing import Any, Dict, List, Optional
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.core.config import settings

logger = logging.getLogger("streamrec.neo4j")

class InMemoryGraphStorage:
    """
    Fallback em memória para demonstração/testes caso o Neo4j não esteja acessível.
    Permite que a aplicação execute 100% das operações graficamente sem travar.
    """
    def __init__(self):
        self.users: Dict[str, dict] = {}
        self.movies: Dict[str, dict] = {}
        self.genres: Dict[str, dict] = {}
        self.watched: List[dict] = []   # {user_id, movie_id, watched_at}
        self.ratings: List[dict] = []   # {user_id, movie_id, rating, comment, rated_at}
        self.movie_genres: List[dict] = [] # {movie_id, genre_name}

    def clear(self):
        self.users.clear()
        self.movies.clear()
        self.genres.clear()
        self.watched.clear()
        self.ratings.clear()
        self.movie_genres.clear()

class Neo4jClient:
    def __init__(self):
        self._driver: Optional[AsyncDriver] = None
        self.is_connected: bool = False
        self.fallback_storage = InMemoryGraphStorage()
        self.mode: str = "uninitialized"

    async def connect(self):
        try:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=1.5,
                max_connection_lifetime=3600,
            )
            # Test connectivity with fast timeout
            async def _check_ping():
                async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
                    res = await session.run("RETURN 1 AS connected")
                    return await res.single()

            record = await asyncio.wait_for(_check_ping(), timeout=2.0)
            if record and record["connected"] == 1:
                self.is_connected = True
                self.mode = "neo4j_live"
                logger.info(" Conexão com Neo4j estabelecida com sucesso em %s", settings.NEO4J_URI)
                await self._init_constraints()
                return
        except Exception as e:
            self.is_connected = False
            if self._driver:
                try:
                    await self._driver.close()
                except Exception:
                    pass
                self._driver = None
            if settings.USE_MOCK_FALLBACK:
                self.mode = "in_memory_fallback"
                logger.warning(
                    " Neo4j não disponível em %s (%s). Utilizando motor gráfico em memória integrado para desenvolvimento/testes.",
                    settings.NEO4J_URI, str(e)
                )
            else:
                logger.error(" Falha ao conectar ao Neo4j: %s", str(e))
                raise

    async def _init_constraints(self):
        """Cria índices e constraints de unicidade no Neo4j."""
        if not self.is_connected or not self._driver:
            return
        constraints = [
            "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT movie_id_unique IF NOT EXISTS FOR (m:Movie) REQUIRE m.id IS UNIQUE",
            "CREATE CONSTRAINT genre_name_unique IF NOT EXISTS FOR (g:Genre) REQUIRE g.name IS UNIQUE"
        ]
        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            for constraint in constraints:
                try:
                    await session.run(constraint)
                except Exception as ex:
                    logger.debug("Constraint check: %s", ex)

    async def close(self):
        if self._driver:
            await self._driver.close()
            self.is_connected = False
            logger.info("Conexão com Neo4j encerrada.")

    async def run_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executa query Cypher no Neo4j real."""
        if not self.is_connected or not self._driver:
            raise RuntimeError("Neo4j driver não está conectado")
        
        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def run_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Executa mutação Cypher no Neo4j real."""
        if not self.is_connected or not self._driver:
            raise RuntimeError("Neo4j driver não está conectado")
        
        async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def health_check(self) -> Dict[str, Any]:
        if self.is_connected and self._driver:
            try:
                async with self._driver.session(database=settings.NEO4J_DATABASE) as session:
                    res = await session.run("RETURN 1 AS ping")
                    await res.single()
                    return {
                        "status": "healthy",
                        "mode": "neo4j_live",
                        "uri": settings.NEO4J_URI,
                        "database": settings.NEO4J_DATABASE
                    }
            except Exception as e:
                return {"status": "unhealthy", "error": str(e), "mode": "neo4j_live"}
        elif self.mode == "in_memory_fallback":
            return {
                "status": "fallback_active",
                "mode": "in_memory_fallback",
                "note": "Operando com grafo em memória (inicie o Neo4j para mudar para neo4j_live)",
                "users_count": len(self.fallback_storage.users),
                "movies_count": len(self.fallback_storage.movies),
                "genres_count": len(self.fallback_storage.genres)
            }
        return {"status": "disconnected"}

neo4j_client = Neo4jClient()
