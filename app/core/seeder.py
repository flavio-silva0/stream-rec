import logging
from typing import Dict, Any
from app.repositories.movie_repo import movie_repo
from app.repositories.user_repo import user_repo
from app.models.schemas import MovieCreate, UserCreate

logger = logging.getLogger("streamrec.seeder")

GENRES = [
    "Ficção Científica",
    "Ação",
    "Drama",
    "Suspense",
    "Crime",
    "Animação",
    "Comédia",
    "Aventura"
]

MOVIES = [
    {"id": "mov-inception", "title": "A Origem (Inception)", "release_year": 2010, "genres": ["Ficção Científica", "Ação", "Suspense"]},
    {"id": "mov-interstellar", "title": "Interestelar", "release_year": 2014, "genres": ["Ficção Científica", "Drama", "Aventura"]},
    {"id": "mov-matrix", "title": "Matrix", "release_year": 1999, "genres": ["Ficção Científica", "Ação"]},
    {"id": "mov-blade-runner", "title": "Blade Runner 2049", "release_year": 2017, "genres": ["Ficção Científica", "Drama", "Suspense"]},
    {"id": "mov-godfather", "title": "O Poderoso Chefão", "release_year": 1972, "genres": ["Crime", "Drama"]},
    {"id": "mov-pulp-fiction", "title": "Pulp Fiction", "release_year": 1994, "genres": ["Crime", "Drama", "Comédia"]},
    {"id": "mov-dark-knight", "title": "Batman: O Cavaleiro das Trevas", "release_year": 2008, "genres": ["Ação", "Crime", "Drama"]},
    {"id": "mov-fight-club", "title": "Clube da Luta", "release_year": 1999, "genres": ["Drama", "Suspense"]},
    {"id": "mov-forrest-gump", "title": "Forrest Gump: O Contador de Histórias", "release_year": 1994, "genres": ["Drama", "Comédia"]},
    {"id": "mov-spirited-away", "title": "A Viagem de Chihiro", "release_year": 2001, "genres": ["Animação", "Aventura"]},
    {"id": "mov-parasite", "title": "Parasita", "release_year": 2019, "genres": ["Suspense", "Drama", "Comédia"]},
    {"id": "mov-gladiator", "title": "Gladiador", "release_year": 2000, "genres": ["Ação", "Aventura", "Drama"]}
]

USERS = [
    {"id": "user-carlos", "name": "Carlos SciFi", "email": "carlos.scifi@streamrec.com"},
    {"id": "user-beatriz", "name": "Beatriz Explorer", "email": "beatriz@streamrec.com"},
    {"id": "user-daniel", "name": "Daniel Classic", "email": "daniel@streamrec.com"},
    {"id": "user-elena", "name": "Elena Nova", "email": "elena@streamrec.com"}
]

# (user_id, movie_id, rating, comment)
RATINGS = [
    # Carlos adora Sci-Fi
    ("user-carlos", "mov-matrix", 5.0, "Uma obra-prima absoluta da ficção científica."),
    ("user-carlos", "mov-inception", 5.0, "Conceito genial e execução primorosa."),
    ("user-carlos", "mov-interstellar", 4.8, "Trilha sonora e física teórica incríveis."),

    # Beatriz tem gosto muito similar ao Carlos em Sci-Fi, mas assistiu mais títulos
    ("user-beatriz", "mov-matrix", 5.0, "Revolucionário."),
    ("user-beatriz", "mov-inception", 4.5, "Excelente trama psicológica."),
    ("user-beatriz", "mov-blade-runner", 4.9, "Visual e narrativa poética de alto nível."),
    ("user-beatriz", "mov-dark-knight", 4.8, "Melhor filme de herói já produzido."),

    # Daniel gosta de Crime e Drama clássicos
    ("user-daniel", "mov-godfather", 5.0, "O clássico supremo do cinema mundial."),
    ("user-daniel", "mov-pulp-fiction", 4.8, "Diálogos espetaculares de Tarantino."),
    ("user-daniel", "mov-fight-club", 4.5, "Final surpreendente e crítica social."),
    ("user-daniel", "mov-parasite", 4.7, "Roteiro impecável."),

    # Elena assistiu poucos filmes (perfil mais novo)
    ("user-elena", "mov-forrest-gump", 4.5, "Emocionante e divertido."),
    ("user-elena", "mov-spirited-away", 5.0, "Animação belíssima e mágica.")
]

WATCHED = [
    ("user-carlos", "mov-matrix"),
    ("user-carlos", "mov-inception"),
    ("user-carlos", "mov-interstellar"),
    ("user-beatriz", "mov-matrix"),
    ("user-beatriz", "mov-inception"),
    ("user-beatriz", "mov-blade-runner"),
    ("user-beatriz", "mov-dark-knight"),
    ("user-daniel", "mov-godfather"),
    ("user-daniel", "mov-pulp-fiction"),
    ("user-daniel", "mov-fight-club"),
    ("user-daniel", "mov-parasite"),
    ("user-elena", "mov-forrest-gump"),
    ("user-elena", "mov-spirited-away")
]

async def seed_database() -> Dict[str, Any]:
    logger.info(" Iniciando população da base de dados...")

    # 1. Gêneros
    genres_count = 0
    for g in GENRES:
        await movie_repo.create_genre(g)
        genres_count += 1

    # 2. Filmes
    movies_count = 0
    for m in MOVIES:
        await movie_repo.create_movie(MovieCreate(**m))
        movies_count += 1

    # 3. Usuários
    users_count = 0
    for u in USERS:
        await user_repo.create_user(UserCreate(**u))
        users_count += 1

    # 4. Filmes Assistidos
    watched_count = 0
    for u_id, m_id in WATCHED:
        await user_repo.record_watched(u_id, m_id)
        watched_count += 1

    # 5. Avaliações
    ratings_count = 0
    for u_id, m_id, rating, comment in RATINGS:
        await user_repo.record_rating(u_id, m_id, rating=rating, comment=comment)
        ratings_count += 1

    logger.info(
        " Base populada com sucesso: %d gêneros, %d filmes, %d usuários, %d visualizações, %d avaliações.",
        genres_count, movies_count, users_count, watched_count, ratings_count
    )

    return {
        "message": "Base de dados populada com sucesso!",
        "genres_created": genres_count,
        "movies_created": movies_count,
        "users_created": users_count,
        "watched_created": watched_count,
        "ratings_created": ratings_count
    }
