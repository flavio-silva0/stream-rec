from typing import List
from fastapi import APIRouter, status
from app.models.schemas import GenreCreate, GenreResponse
from app.repositories.movie_repo import movie_repo

router = APIRouter(prefix="/genres", tags=["Gêneros"])

@router.post("/", response_model=GenreResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar novo gênero")
async def create_genre(genre_in: GenreCreate):
    """
    Registra um novo gênero de filme no banco de grafos Neo4j.
    """
    return await movie_repo.create_genre(genre_in.name)

@router.get("/", response_model=List[GenreResponse], summary="Listar todos os gêneros")
async def list_genres():
    """
    Retorna a lista de gêneros cadastrados e a quantidade de filmes vinculados.
    """
    return await movie_repo.list_genres()
