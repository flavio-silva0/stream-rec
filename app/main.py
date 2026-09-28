import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.database.neo4j_client import neo4j_client
from app.database.redis_client import redis_client
from app.core.seeder import seed_database
from app.repositories.movie_repo import movie_repo
from app.routers import (
    recommendations_router,
    users_router,
    movies_router,
    genres_router,
    cache_router,
    health_router
)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("streamrec.main")

tags_metadata = [
    {
        "name": "Recomendações",
        "description": "Motor de recomendação personalizada com algoritmos de grafos no Neo4j (Colaborativa, Afinidade por Gênero, Trending e Híbrida) e aceleração de cache Redis com TTL.",
    },
    {
        "name": "Usuários",
        "description": "Cadastro de usuários e registro de interações (filmes assistidos e avaliações de 1.0 a 5.0) com invalidação automática de cache.",
    },
    {
        "name": "Filmes",
        "description": "Gerenciamento do catálogo de filmes cinematográficos e consulta de avaliações médias.",
    },
    {
        "name": "Gêneros",
        "description": "Gerenciamento de gêneros de filmes no grafo do Neo4j.",
    },
    {
        "name": "Cache Redis",
        "description": "Monitoramento em tempo real de CACHE HIT / MISS, taxa de acerto (%) e expurgo manual de chaves.",
    },
    {
        "name": "Sistema & Saúde",
        "description": "Diagnóstico de conectividade com Neo4j/Redis e inicializador de dados de demonstração.",
    },
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(" Iniciando plataforma StreamRec...")
    # 1. Conecta aos bancos
    await neo4j_client.connect()
    await redis_client.connect()

    # 2. Popula automaticamente se a base estiver vazia
    try:
        movies = await movie_repo.list_movies()
        if len(movies) == 0:
            logger.info(" Base de dados vazia detectada. Executando seed inicial automático...")
            await seed_database()
    except Exception as e:
        logger.warning("Não foi possível verificar seed inicial automático: %s", e)

    yield

    logger.info(" Encerrando conexões da plataforma StreamRec...")
    await neo4j_client.close()
    await redis_client.close()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Habilitar CORS para permitir consumo por frontends web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar Rotas priorizando o core de negócio
app.include_router(recommendations_router)
app.include_router(users_router)
app.include_router(movies_router)
app.include_router(genres_router)
app.include_router(cache_router)
app.include_router(health_router)

@app.get("/", include_in_schema=False)
async def root():
    """Redireciona para a documentação interativa Swagger."""
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
