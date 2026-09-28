from fastapi import APIRouter, Query
from app.database.neo4j_client import neo4j_client
from app.database.redis_client import redis_client
from app.core.config import settings
from app.core.seeder import seed_database
from app.models.schemas import HealthResponse, SeedResponse, Neo4jHealthStatus, RedisHealthStatus

router = APIRouter(tags=["Sistema & Saúde"])

@router.get("/health", response_model=HealthResponse, summary="Verificação de integridade dos serviços")
async def health_check():
    """
    Verifica a conectividade e status operacional dos componentes:
    - **API FastAPI**: Status geral da aplicação
    - **Banco de Grafos Neo4j**: Conexão com Bolt e estatísticas de nós
    - **Cache Redis**: Conexão in-memory e TTL configurado
    """
    neo4j_data = await neo4j_client.health_check()
    redis_data = await redis_client.health_check()
    
    overall_status = "healthy"
    if neo4j_data.get("status") == "unhealthy" or redis_data.get("status") == "unhealthy":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        neo4j=Neo4jHealthStatus(**neo4j_data),
        redis=RedisHealthStatus(**redis_data),
        version=settings.VERSION
    )

@router.post("/seed", response_model=SeedResponse, summary="Popular banco com dados de exemplo")
async def seed_data(
    reset_cache: bool = Query(
        True,
        description="Se marcado, limpa o cache do Redis após o povoamento para garantir frescor total"
    )
):
    """
    Povoa o Neo4j com gêneros, filmes do catálogo, perfis de usuários, filmes assistidos e avaliações.
    Útil para testes imediatos das recomendações e benchmarks.
    """
    result = await seed_database()
    if reset_cache:
        await redis_client.clear_all()
    return SeedResponse(**result)
