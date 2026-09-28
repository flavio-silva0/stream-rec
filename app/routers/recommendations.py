from inspect import cleandoc
from typing import Optional, Literal
from fastapi import APIRouter, Query, Path, Response, HTTPException, status
from app.models.schemas import RecommendationResponse
from app.services.recommendation_service import recommendation_service
from app.repositories.user_repo import user_repo

router = APIRouter(prefix="/recommendations", tags=["Recomendações"])

@router.get(
    "/{user_id}",
    response_model=RecommendationResponse,
    summary="Gerar recomendações personalizadas com Cache",
    description=cleandoc("""
    Gera recomendações de filmes personalizadas para um determinado usuário com estratégia de Cache Redis (TTL):

    * **1ª Chamada (CACHE MISS)**: A consulta é executada no banco de grafos Neo4j (via Cypher), o resultado é serializado e armazenado no Redis com o TTL definido. O cabeçalho `X-Cache: MISS` é retornado.
    * **Chamadas Seguintes (CACHE HIT)**: A recomendação é recuperada instantaneamente da memória do Redis. O cabeçalho `X-Cache: HIT` é retornado com o tempo restante do TTL.

    **Estratégias disponíveis:**
    * `hybrid`: Combina Filtragem Colaborativa (usuários similares) + Afinidade por Gênero + Filmes em Alta (Padrão).
    * `collaborative`: Recomendações baseadas em outros usuários que gostaram dos mesmos filmes que você.
    * `genre`: Baseado nos gêneros mais consumidos e melhor avaliados pelo usuário.
    * `trending`: Filmes populares mais bem avaliados no catálogo (ideal para novos usuários / Cold Start).
    """)
)
async def get_user_recommendations(
    response: Response,
    user_id: str = Path(
        ...,
        examples=["user-carlos"],
        description="ID do usuário para o qual gerar recomendações (ex: user-carlos, user-beatriz, user-daniel, user-elena)"
    ),
    strategy: Literal["hybrid", "collaborative", "genre", "trending"] = Query(
        "hybrid",
        description="Estratégia do algoritmo de recomendação"
    ),
    limit: int = Query(5, ge=1, le=50, description="Quantidade máxima de filmes recomendados"),
    bypass_cache: bool = Query(False, description="Forçar consulta ao banco Neo4j ignorando o cache Redis")
):
    user = await user_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário com ID '{user_id}' não encontrado."
        )

    rec_response, cache_status = await recommendation_service.get_recommendations(
        user_id=user_id,
        strategy=strategy,
        limit=limit,
        bypass_cache=bypass_cache
    )

    # Injeta cabeçalhos HTTP para inspeção de cache e latência
    response.headers["X-Cache"] = cache_status
    response.headers["X-Response-Time-Ms"] = str(rec_response.response_time_ms)
    if rec_response.ttl_remaining_seconds is not None:
        response.headers["X-Cache-TTL"] = str(rec_response.ttl_remaining_seconds)

    return rec_response
