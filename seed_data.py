"""
Script utilitário para popular a base de dados do Neo4j e Redis via linha de comando.
Execução:
    python seed_data.py
"""
import sys
import asyncio
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.database.neo4j_client import neo4j_client
from app.database.redis_client import redis_client
from app.core.seeder import seed_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    print("=" * 60)
    print("🎬 StreamRec - Inicializador de Dados (Neo4j & Redis)")
    print("=" * 60)
    
    await neo4j_client.connect()
    await redis_client.connect()
    
    res = await seed_database()
    print(f"Sucesso: {res['message']}")
    print(f"- Gêneros criados: {res['genres_created']}")
    print(f"- Filmes criados: {res['movies_created']}")
    print(f"- Usuários criados: {res['users_created']}")
    print(f"- Visualizações registradas: {res['watched_created']}")
    print(f"- Avaliações registradas: {res['ratings_created']}")
    
    # Limpa cache do Redis para garantir frescor
    await redis_client.clear_all()
    print("- Cache do Redis limpo.")
    
    await neo4j_client.close()
    await redis_client.close()
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
