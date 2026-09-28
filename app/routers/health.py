from fastapi import APIRouter
from app.database.neo4j_client import neo4j_client
from app.database.redis_client import redis_client
from app.core.config import settings
from app.core.seeder import seed_database
from app.models.schemas import HealthResponse, SeedResponse

router = APIRouter(tags=["Sistema & Saúde"])

@router.get("/health", response_model=HealthResponse, summary="Verificação de integridade dos serviços")
async def health_check():
    """
    Verifica a conectividade e status operacional dos componentes:
    - API FastAPI
    - Banco de Grafos Neo4j
    - Cache Redis
    """
    neo4j_health = await neo4j_client.health_check()
    redis_health = await redis_client.health_check()
    
    overall_status = "healthy"
    if neo4j_health.get("status") == "unhealthy" or redis_health.get("status") == "unhealthy":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        neo4j=neo4j_health,
        redis=redis_health,
        version=settings.VERSION
    )

@router.post("/seed", response_model=SeedResponse, summary="Popular banco com dados de exemplo")
async def seed_data():
    """
    Povoa o Neo4j com gêneros, filmes do catálogo, perfis de usuários, filmes assistidos e avaliações.
    Útil para testes imediatos das recomendações e benchmarks.
    """
    result = await seed_database()
    return SeedResponse(**result)
