from typing import List
from fastapi import APIRouter, HTTPException, status
from app.models.schemas import MovieCreate, MovieResponse
from app.repositories.movie_repo import movie_repo

router = APIRouter(prefix="/movies", tags=["Filmes"])

@router.post("/", response_model=MovieResponse, status_code=status.HTTP_201_CREATED, summary="Cadastrar novo filme")
async def create_movie(movie_in: MovieCreate):
    """
    Cadastra um novo filme no catálogo e conecta-o aos seus respectivos gêneros no Neo4j.
    """
    return await movie_repo.create_movie(movie_in)

@router.get("/", response_model=List[MovieResponse], summary="Listar catálogo de filmes")
async def list_movies():
    """
    Retorna a listagem de filmes disponíveis com seus gêneros e média de avaliações.
    """
    return await movie_repo.list_movies()

@router.get("/{movie_id}", response_model=MovieResponse, summary="Obter detalhes de um filme")
async def get_movie(movie_id: str):
    """
    Retorna os detalhes de um filme específico pelo ID.
    """
    movie = await movie_repo.get_movie_by_id(movie_id)
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filme com ID '{movie_id}' não encontrado."
        )
    return movie
