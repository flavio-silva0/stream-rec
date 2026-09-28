import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.neo4j_client import neo4j_client
from app.database.redis_client import redis_client

@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialize_test_databases():
    """Garante que as conexões (ou fallbacks) estejam ativas durante toda a suíte de testes."""
    await neo4j_client.connect()
    await redis_client.connect()
    yield
    await neo4j_client.close()
    await redis_client.close()

@pytest_asyncio.fixture(autouse=True)
async def setup_teardown():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Povoar dados iniciais
        await client.post("/seed")
        # Limpar cache antes de cada teste
        await client.delete("/cache/all")
        yield
        # Limpar cache após cada teste
        await client.delete("/cache/all")

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "neo4j" in data
        assert "redis" in data
        assert data["redis"]["status"] == "healthy"

@pytest.mark.asyncio
async def test_create_user_and_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_payload = {
            "id": "user-test-marcos",
            "name": "Marcos Teste",
            "email": "marcos@teste.com"
        }
        res = await client.post("/users/", json=user_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["id"] == "user-test-marcos"
        assert data["name"] == "Marcos Teste"

        # Listar usuários
        res_list = await client.get("/users/")
        assert res_list.status_code == 200
        users = res_list.json()
        assert any(u["id"] == "user-test-marcos" for u in users)

@pytest.mark.asyncio
async def test_create_genre_and_movie():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Cadastrar gênero
        res_g = await client.post("/genres/", json={"name": "Cyberpunk"})
        assert res_g.status_code == 201

        # Cadastrar filme
        movie_payload = {
            "id": "mov-cyberpunk-edgerunners",
            "title": "Cyberpunk: Edgerunners",
            "release_year": 2022,
            "genres": ["Cyberpunk", "Ação", "Animação"]
        }
        res_m = await client.post("/movies/", json=movie_payload)
        assert res_m.status_code == 201
        m_data = res_m.json()
        assert m_data["id"] == "mov-cyberpunk-edgerunners"
        assert "Cyberpunk" in m_data["genres"]

@pytest.mark.asyncio
async def test_record_watched_and_rating():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Registrar filme assistido
        res_w = await client.post("/users/user-carlos/watched", json={
            "movie_id": "mov-fight-club"
        })
        assert res_w.status_code == 201
        w_data = res_w.json()
        assert w_data["user_id"] == "user-carlos"
        assert w_data["movie_id"] == "mov-fight-club"
        assert w_data["cache_invalidated"] is True

        # Registrar avaliação
        res_r = await client.post("/users/user-carlos/ratings", json={
            "movie_id": "mov-fight-club",
            "rating": 4.5,
            "comment": "Roteiro instigante!"
        })
        assert res_r.status_code == 201
        r_data = res_r.json()
        assert r_data["rating"] == 4.5
        assert r_data["comment"] == "Roteiro instigante!"
        assert r_data["cache_invalidated"] is True

@pytest.mark.asyncio
async def test_cache_miss_then_cache_hit_and_ttl():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1ª Chamada: Espera-se CACHE MISS (pesquisa Neo4j e grava no Redis)
        res1 = await client.get("/recommendations/user-carlos?strategy=hybrid&limit=4")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["cache_status"] == "CACHE MISS"
        assert res1.headers.get("X-Cache") == "MISS"
        assert data1["ttl_remaining_seconds"] is not None
        assert len(data1["data"]) > 0

        # 2ª Chamada: Espera-se CACHE HIT (retirado diretamente da memória do Redis)
        res2 = await client.get("/recommendations/user-carlos?strategy=hybrid&limit=4")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["cache_status"] == "CACHE HIT"
        assert res2.headers.get("X-Cache") == "HIT"
        assert data2["ttl_remaining_seconds"] is not None
        assert data2["ttl_remaining_seconds"] > 0
        # Os itens recomendados devem ser exatamente idênticos
        assert len(data2["data"]) == len(data1["data"])
        assert data2["data"][0]["movie_id"] == data1["data"][0]["movie_id"]

@pytest.mark.asyncio
async def test_cache_invalidation_on_new_rating():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Passo 1: Aquecer o cache (MISS -> HIT)
        await client.get("/recommendations/user-beatriz?strategy=hybrid")
        hit_res = await client.get("/recommendations/user-beatriz?strategy=hybrid")
        assert hit_res.json()["cache_status"] == "CACHE HIT"

        # Passo 2: Beatriz avalia um novo filme -> deve invalidar o cache
        await client.post("/users/user-beatriz/ratings", json={
            "movie_id": "mov-godfather",
            "rating": 5.0,
            "comment": "Fantástico clássico"
        })

        # Passo 3: Próxima chamada de recomendação DEVE ser CACHE MISS!
        after_invalidation = await client.get("/recommendations/user-beatriz?strategy=hybrid")
        assert after_invalidation.status_code == 200
        assert after_invalidation.json()["cache_status"] == "CACHE MISS"
        assert after_invalidation.headers.get("X-Cache") == "MISS"

@pytest.mark.asyncio
async def test_manual_cache_invalidation_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Aquecer cache
        await client.get("/recommendations/user-daniel?strategy=collaborative")
        hit_res = await client.get("/recommendations/user-daniel?strategy=collaborative")
        assert hit_res.json()["cache_status"] == "CACHE HIT"

        # Invalidar manualmente via DELETE /cache/user/{id}
        del_res = await client.delete("/cache/user/user-daniel")
        assert del_res.status_code == 200
        assert del_res.json()["keys_removed"] >= 1

        # Próxima chamada deve ser MISS
        miss_res = await client.get("/recommendations/user-daniel?strategy=collaborative")
        assert miss_res.json()["cache_status"] == "CACHE MISS"
