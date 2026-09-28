"""
Benchmark de Desempenho - Plataforma de Recomendação (Neo4j + Redis)
Compara latência, throughput e taxa de acerto entre CACHE MISS (Neo4j) e CACHE HIT (Redis).

Pode ser executado com servidor rodando ou diretamente via ASGI client:
    python benchmark.py
"""
import sys
import time
import json
import statistics
import asyncio
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import httpx
from app.main import app
from app.database.neo4j_client import neo4j_client
from app.database.redis_client import redis_client

USERS = ["user-carlos", "user-beatriz", "user-daniel", "user-elena"]
STRATEGIES = ["hybrid", "collaborative", "genre", "trending"]

def compute_stats(latencies: List[float]) -> Dict[str, float]:
    if not latencies:
        return {}
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    p50_idx = int(0.50 * n)
    p95_idx = min(int(0.95 * n), n - 1)
    p99_idx = min(int(0.99 * n), n - 1)
    
    return {
        "count": n,
        "min_ms": round(min(sorted_lats), 2),
        "max_ms": round(max(sorted_lats), 2),
        "mean_ms": round(statistics.mean(sorted_lats), 2),
        "median_ms": round(sorted_lats[p50_idx], 2),
        "p95_ms": round(sorted_lats[p95_idx], 2),
        "p99_ms": round(sorted_lats[p99_idx], 2),
        "std_dev": round(statistics.stdev(sorted_lats) if n > 1 else 0.0, 2)
    }

async def run_benchmark(target_url: str = None, iterations_miss: int = 40, iterations_hit: int = 100):
    print("=" * 75)
    print("🚀 INICIANDO TESTES DE DESEMPENHO: Neo4j (Grafo) vs Redis (Cache)")
    print("=" * 75)

    # Inicializar clientes
    await neo4j_client.connect()
    await redis_client.connect()

    # Se target_url for informado, usa cliente HTTP externo; senão ASGI in-process
    if target_url:
        client = httpx.AsyncClient(base_url=target_url, timeout=30.0)
        mode_desc = f"Servidor HTTP Externo ({target_url})"
    else:
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://streamrec.test", timeout=30.0)
        mode_desc = "Transporte ASGI In-Process (App Direta)"

    print(f"Modo de Execução: {mode_desc}")

    async with client:
        # 1. Povoamento dos dados
        print("\n[1/4] Populando base de dados com seed de teste...")
        seed_res = await client.post("/seed")
        print(f"       -> Status: {seed_res.status_code} ({seed_res.json().get('message')})")

        # 2. Benchmark de CACHE MISS (Consultas ao Banco de Grafos)
        print(f"\n[2/4] Executando {iterations_miss} requisições de CACHE MISS (Neo4j)...")
        miss_latencies: List[float] = []
        miss_start = time.perf_counter()

        for i in range(iterations_miss):
            u_id = USERS[i % len(USERS)]
            strat = STRATEGIES[i % len(STRATEGIES)]
            
            # Limpa cache antes ou usa bypass para forçar MISS
            t0 = time.perf_counter()
            resp = await client.get(f"/recommendations/{u_id}?strategy={strat}&limit=5&bypass_cache=true")
            t_elapsed = (time.perf_counter() - t0) * 1000
            
            if resp.status_code == 200:
                miss_latencies.append(t_elapsed)
            else:
                print(f"Erro MISS req {i}: {resp.status_code}")

        total_miss_time = time.perf_counter() - miss_start
        miss_rps = round(len(miss_latencies) / total_miss_time, 2)
        miss_stats = compute_stats(miss_latencies)
        print(f"       -> Média MISS: {miss_stats['mean_ms']} ms | p95: {miss_stats['p95_ms']} ms | Throughput: {miss_rps} req/s")

        # 3. Aquecimento e Benchmark de CACHE HIT (Redis)
        print(f"\n[3/4] Aquecendo o cache e executando {iterations_hit} requisições de CACHE HIT (Redis)...")
        # Aquecer para todos os usuários e estratégias
        for u in USERS:
            for s in STRATEGIES:
                await client.get(f"/recommendations/{u}?strategy={s}&limit=5")

        hit_latencies: List[float] = []
        hit_start = time.perf_counter()

        for i in range(iterations_hit):
            u_id = USERS[i % len(USERS)]
            strat = STRATEGIES[i % len(STRATEGIES)]
            
            t0 = time.perf_counter()
            resp = await client.get(f"/recommendations/{u_id}?strategy={strat}&limit=5")
            t_elapsed = (time.perf_counter() - t0) * 1000
            
            if resp.status_code == 200:
                assert resp.headers.get("X-Cache") == "HIT", "Esperado CACHE HIT"
                hit_latencies.append(t_elapsed)
            else:
                print(f"Erro HIT req {i}: {resp.status_code}")

        total_hit_time = time.perf_counter() - hit_start
        hit_rps = round(len(hit_latencies) / total_hit_time, 2)
        hit_stats = compute_stats(hit_latencies)
        print(f"       -> Média HIT:  {hit_stats['mean_ms']} ms | p95: {hit_stats['p95_ms']} ms | Throughput: {hit_rps} req/s")

        # 4. Estatísticas finais do Redis
        print("\n[4/4] Coletando métricas do Redis...")
        cache_stats_res = await client.get("/cache/stats")
        cache_stats = cache_stats_res.json()

    # Cálculos comparativos
    speedup = round(miss_stats["mean_ms"] / hit_stats["mean_ms"], 2) if hit_stats["mean_ms"] > 0 else 0
    reduction_pct = round(((miss_stats["mean_ms"] - hit_stats["mean_ms"]) / miss_stats["mean_ms"]) * 100, 2)
    p95_speedup = round(miss_stats["p95_ms"] / hit_stats["p95_ms"], 2) if hit_stats["p95_ms"] > 0 else 0

    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode_desc,
        "cache_miss_neo4j": {
            **miss_stats,
            "throughput_rps": miss_rps
        },
        "cache_hit_redis": {
            **hit_stats,
            "throughput_rps": hit_rps
        },
        "comparison": {
            "speedup_factor": f"{speedup}x mais rápido",
            "latency_reduction_pct": f"{reduction_pct}%",
            "p95_speedup": f"{p95_speedup}x"
        },
        "redis_metrics": cache_stats
    }

    # Salva relatório em arquivo JSON
    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Exibe Relatório Formatado
    print("\n" + "=" * 75)
    print("📊 RESULTADOS DO BENCHMARK DE DESEMPENHO")
    print("=" * 75)
    print(f"{'Métrica':<25} | {'CACHE MISS (Neo4j)':<20} | {'CACHE HIT (Redis)':<20}")
    print("-" * 75)
    print(f"{'Amostras (Requisições)':<25} | {miss_stats['count']:<20} | {hit_stats['count']:<20}")
    print(f"{'Latência Média':<25} | {miss_stats['mean_ms']:<17} ms | {hit_stats['mean_ms']:<17} ms")
    print(f"{'Mediana (p50)':<25} | {miss_stats['median_ms']:<17} ms | {hit_stats['median_ms']:<17} ms")
    print(f"{'Percentil 95 (p95)':<25} | {miss_stats['p95_ms']:<17} ms | {hit_stats['p95_ms']:<17} ms")
    print(f"{'Percentil 99 (p99)':<25} | {miss_stats['p99_ms']:<17} ms | {hit_stats['p99_ms']:<17} ms")
    print(f"{'Mínima':<25} | {miss_stats['min_ms']:<17} ms | {hit_stats['min_ms']:<17} ms")
    print(f"{'Máxima':<25} | {miss_stats['max_ms']:<17} ms | {hit_stats['max_ms']:<17} ms")
    print(f"{'Throughput (req/s)':<25} | {miss_rps:<17} rps| {hit_rps:<17} rps")
    print("-" * 75)
    print(f"⚡ Fator de Aceleração (Speedup):    {speedup}x")
    print(f"📉 Redução na Latência de Resposta:  {reduction_pct}%")
    print(f"🎯 Taxa de Acerto de Cache (Hit Rate): {cache_stats.get('hit_rate_pct', 0)}%")
    print(f"💾 Chaves Armazenadas no Redis:      {cache_stats.get('keys_count', 0)}")
    print("=" * 75)
    print("📁 Relatório salvo com sucesso em: benchmark_results.json")
    print("=" * 75)

    await neo4j_client.close()
    await redis_client.close()

if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(run_benchmark(url_arg))
