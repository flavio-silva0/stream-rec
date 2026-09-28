import logging
from typing import List
from fastapi import APIRouter, HTTPException, Path, status
from app.models.schemas import (
    UserCreate, UserResponse, UserDetailResponse,
    WatchedCreate, WatchedResponse, RatingCreate, RatingResponse
)
from app.repositories.user_repo import user_repo
from app.repositories.movie_repo import movie_repo
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger("streamrec.routers.users")
router = APIRouter(prefix="/users", tags=["Usuários"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar novo usuário")
async def create_user(user_in: UserCreate):
    """
    Cadastra um novo usuário no banco de grafos Neo4j.
    Se o ID não for informado, um identificador único será gerado.
    """
    user = await user_repo.create_user(user_in)
    return user

@router.get("/", response_model=List[UserResponse], summary="Listar todos os usuários")
async def list_users():
    """
    Retorna a lista de todos os usuários cadastrados e a contagem de interações.
    """
    return await user_repo.list_users()

@router.get("/{user_id}", response_model=UserDetailResponse, summary="Obter detalhes do usuário")
async def get_user_details(
    user_id: str = Path(..., examples=["user-carlos"], description="ID do usuário (ex: user-carlos, user-beatriz)")
):
    """
    Retorna o perfil completo do usuário, incluindo lista de filmes assistidos e avaliações realizadas.
    """
    user = await user_repo.get_user_details(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário com ID '{user_id}' não encontrado."
        )
    return user

@router.post("/{user_id}/watched", response_model=WatchedResponse, status_code=status.HTTP_201_CREATED, summary="Registrar filme assistido")
async def record_watched(
    watched_in: WatchedCreate,
    user_id: str = Path(..., examples=["user-carlos"], description="ID do usuário que assistiu ao filme")
):
    """
    Registra que o usuário assistiu a um filme no Neo4j criando a relação `(:User)-[:WATCHED]->(:Movie)`.
    **Importante**: Esta ação invalida automaticamente o cache de recomendações deste usuário no Redis.
    """
    user = await user_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuário '{user_id}' não encontrado.")

    movie = await movie_repo.get_movie_by_id(watched_in.movie_id)
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Filme '{watched_in.movie_id}' não encontrado.")

    res = await user_repo.record_watched(user_id, watched_in.movie_id, watched_in.watched_at)
    # Invalidação de Cache
    await recommendation_service.invalidate_user_cache(user_id)
    return res

@router.post("/{user_id}/ratings", response_model=RatingResponse, status_code=status.HTTP_201_CREATED, summary="Registrar avaliação de filme")
async def record_rating(
    rating_in: RatingCreate,
    user_id: str = Path(..., examples=["user-carlos"], description="ID do usuário que está avaliando o filme")
):
    """
    Registra uma avaliação (nota de 1.0 a 5.0 e comentário opcional) no Neo4j `(:User)-[:RATED]->(:Movie)`.
    **Importante**: Esta ação invalida automaticamente o cache de recomendações deste usuário no Redis,
    garantindo que novas recomendações reflitam as preferências atualizadas.
    """
    user = await user_repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuário '{user_id}' não encontrado.")

    movie = await movie_repo.get_movie_by_id(rating_in.movie_id)
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Filme '{rating_in.movie_id}' não encontrado.")

    res = await user_repo.record_rating(
        user_id,
        rating_in.movie_id,
        rating_in.rating,
        rating_in.comment,
        rating_in.rated_at
    )
    # Invalidação de Cache
    await recommendation_service.invalidate_user_cache(user_id)
    return res
