import logging
from typing import List, Dict, Any, Optional
from app.database.neo4j_client import neo4j_client
from app.models.schemas import RecommendationItem

logger = logging.getLogger("streamrec.recommendation")

class RecommendationRepository:
    async def get_user_collaborative_recommendations(self, user_id: str, limit: int = 5) -> List[RecommendationItem]:
        """
        Filtragem Colaborativa baseada em Grafo:
        Identifica usuários que avaliaram positivamente (>= 3.0) os mesmos filmes que o usuário alvo,
        e recomenda filmes que esses usuários afins avaliaram com nota >= 3.5 que o usuário alvo ainda não viu.
        """
        if neo4j_client.is_connected:
            query = """
            MATCH (u:User {id: $user_id})-[r1:RATED]->(common:Movie)<-[r2:RATED]-(similarUser:User)
            WHERE u <> similarUser AND r1.rating >= 3.0 AND r2.rating >= 3.0
            MATCH (similarUser)-[r3:RATED]->(rec:Movie)
            WHERE r3.rating >= 3.5
              AND NOT (u)-[:WATCHED]->(rec)
              AND NOT (u)-[:RATED]->(rec)
            OPTIONAL MATCH (rec)-[:BELONGS_TO]->(g:Genre)
            WITH rec,
                 collect(DISTINCT g.name) AS genres,
                 count(DISTINCT similarUser) AS similar_user_count,
                 avg(r3.rating) AS avg_sim_rating
            RETURN rec.id AS movie_id,
                   rec.title AS title,
                   rec.release_year AS release_year,
                   genres,
                   round(avg_sim_rating, 2) AS predicted_rating,
                   round((similar_user_count * 0.4 + avg_sim_rating * 0.6), 2) AS score,
                   'Recomendado com base nas avaliações de ' + toString(similar_user_count) + ' usuário(s) com gostos afins' AS reason
            ORDER BY score DESC, similar_user_count DESC
            LIMIT $limit
            """
            records = await neo4j_client.run_query(query, {"user_id": user_id, "limit": limit})
            return [
                RecommendationItem(
                    movie_id=row["movie_id"],
                    title=row["title"],
                    release_year=row["release_year"],
                    genres=row["genres"] or [],
                    predicted_rating=float(row["predicted_rating"]),
                    score=float(row["score"]),
                    reason=row["reason"]
                )
                for row in records
            ]
        else:
            return self._fallback_collaborative(user_id, limit)

    async def get_user_genre_recommendations(self, user_id: str, limit: int = 5) -> List[RecommendationItem]:
        """
        Recomendação Baseada em Conteúdo / Afinidade de Gênero:
        Analisa os gêneros que o usuário mais consumiu e melhor avaliou,
        e recomenda os melhores filmes desses gêneros que ele ainda não assistiu.
        """
        if neo4j_client.is_connected:
            query = """
            MATCH (u:User {id: $user_id})-[r:RATED]->(watchedMovie:Movie)-[:BELONGS_TO]->(favGenre:Genre)
            WHERE r.rating >= 3.0
            WITH u, favGenre, count(*) AS genre_weight, avg(r.rating) AS avg_genre_rating
            ORDER BY genre_weight DESC, avg_genre_rating DESC
            LIMIT 3
            MATCH (rec:Movie)-[:BELONGS_TO]->(favGenre)
            WHERE NOT (u)-[:WATCHED]->(rec)
              AND NOT (u)-[:RATED]->(rec)
            OPTIONAL MATCH (rec)-[:BELONGS_TO]->(allGenres:Genre)
            OPTIONAL MATCH (:User)-[allRatings:RATED]->(rec)
            WITH rec,
                 collect(DISTINCT allGenres.name) AS genres,
                 favGenre.name AS matched_genre,
                 coalesce(round(avg(allRatings.rating), 2), 4.0) AS avg_rating
            RETURN rec.id AS movie_id,
                   rec.title AS title,
                   rec.release_year AS release_year,
                   genres,
                   avg_rating AS predicted_rating,
                   avg_rating AS score,
                   'Porque você tem afinidade com o gênero ' + matched_genre AS reason
            ORDER BY score DESC
            LIMIT $limit
            """
            records = await neo4j_client.run_query(query, {"user_id": user_id, "limit": limit})
            return [
                RecommendationItem(
                    movie_id=row["movie_id"],
                    title=row["title"],
                    release_year=row["release_year"],
                    genres=row["genres"] or [],
                    predicted_rating=float(row["predicted_rating"]),
                    score=float(row["score"]),
                    reason=row["reason"]
                )
                for row in records
            ]
        else:
            return self._fallback_genre(user_id, limit)

    async def get_trending_recommendations(self, user_id: str, limit: int = 5) -> List[RecommendationItem]:
        """
        Recomendação Global / Popularidade (Cold Start):
        Filmes mais bem avaliados e mais assistidos do catálogo que o usuário ainda não viu.
        """
        if neo4j_client.is_connected:
            query = """
            MATCH (rec:Movie)
            WHERE NOT (:User {id: $user_id})-[:WATCHED]->(rec)
              AND NOT (:User {id: $user_id})-[:RATED]->(rec)
            OPTIONAL MATCH (rec)-[:BELONGS_TO]->(g:Genre)
            OPTIONAL MATCH (:User)-[r:RATED]->(rec)
            OPTIONAL MATCH (:User)-[w:WATCHED]->(rec)
            WITH rec,
                 collect(DISTINCT g.name) AS genres,
                 count(DISTINCT r) AS rating_count,
                 count(DISTINCT w) AS watched_count,
                 coalesce(round(avg(r.rating), 2), 4.0) AS avg_rating
            RETURN rec.id AS movie_id,
                   rec.title AS title,
                   rec.release_year AS release_year,
                   genres,
                   avg_rating AS predicted_rating,
                   round((avg_rating * 0.7 + (rating_count + watched_count) * 0.1), 2) AS score,
                   'Destaque popular e bem avaliado no catálogo' AS reason
            ORDER BY score DESC, rating_count DESC
            LIMIT $limit
            """
            records = await neo4j_client.run_query(query, {"user_id": user_id, "limit": limit})
            return [
                RecommendationItem(
                    movie_id=row["movie_id"],
                    title=row["title"],
                    release_year=row["release_year"],
                    genres=row["genres"] or [],
                    predicted_rating=float(row["predicted_rating"]),
                    score=float(row["score"]),
                    reason=row["reason"]
                )
                for row in records
            ]
        else:
            return self._fallback_trending(user_id, limit)

    async def get_hybrid_recommendations(self, user_id: str, limit: int = 5) -> List[RecommendationItem]:
        """
        Abordagem Híbrida:
        1. Executa Filtragem Colaborativa (máxima personalização baseada em grafos)
        2. Se houver vagas, complementa com Afinidade por Gênero
        3. Se ainda faltar, preenche com Filmes em Alta (Cold Start)
        Garante catálogo rico e sem duplicidades.
        """
        seen_movie_ids = set()
        results: List[RecommendationItem] = []

        # 1. Colaborativa
        collab = await self.get_user_collaborative_recommendations(user_id, limit=limit)
        for item in collab:
            if item.movie_id not in seen_movie_ids:
                seen_movie_ids.add(item.movie_id)
                results.append(item)
            if len(results) >= limit:
                return results

        # 2. Gênero
        if len(results) < limit:
            genre_recs = await self.get_user_genre_recommendations(user_id, limit=limit)
            for item in genre_recs:
                if item.movie_id not in seen_movie_ids:
                    seen_movie_ids.add(item.movie_id)
                    results.append(item)
                if len(results) >= limit:
                    return results

        # 3. Trending / Cold Start
        if len(results) < limit:
            trending = await self.get_trending_recommendations(user_id, limit=limit)
            for item in trending:
                if item.movie_id not in seen_movie_ids:
                    seen_movie_ids.add(item.movie_id)
                    results.append(item)
                if len(results) >= limit:
                    return results

        return results

    # ==================== Métodos Fallback em Memória ====================
    def _get_watched_or_rated_ids(self, user_id: str) -> set:
        storage = neo4j_client.fallback_storage
        seen = {w["movie_id"] for w in storage.watched if w["user_id"] == user_id}
        seen.update({r["movie_id"] for r in storage.ratings if r["user_id"] == user_id})
        return seen

    def _fallback_collaborative(self, user_id: str, limit: int) -> List[RecommendationItem]:
        storage = neo4j_client.fallback_storage
        user_ratings = {r["movie_id"]: r["rating"] for r in storage.ratings if r["user_id"] == user_id and r["rating"] >= 3.0}
        if not user_ratings:
            return []

        seen_movies = self._get_watched_or_rated_ids(user_id)

        # Encontra usuários que avaliaram os mesmos filmes positivamente
        similar_users = {}
        for r in storage.ratings:
            if r["user_id"] != user_id and r["movie_id"] in user_ratings and r["rating"] >= 3.0:
                similar_users[r["user_id"]] = similar_users.get(r["user_id"], 0) + 1

        if not similar_users:
            return []

        # Coleta filmes recomendados
        candidates = {}
        for r in storage.ratings:
            sim_u = r["user_id"]
            m_id = r["movie_id"]
            if sim_u in similar_users and m_id not in seen_movies and r["rating"] >= 3.5:
                if m_id not in candidates:
                    candidates[m_id] = {"ratings": [], "users": set()}
                candidates[m_id]["ratings"].append(r["rating"])
                candidates[m_id]["users"].add(sim_u)

        results = []
        for m_id, data in candidates.items():
            m = storage.movies.get(m_id)
            if not m:
                continue
            genres = [mg["genre_name"] for mg in storage.movie_genres if mg["movie_id"] == m_id]
            avg_r = round(sum(data["ratings"]) / len(data["ratings"]), 2)
            u_count = len(data["users"])
            score = round(u_count * 0.4 + avg_r * 0.6, 2)
            results.append(
                RecommendationItem(
                    movie_id=m_id,
                    title=m["title"],
                    release_year=m["release_year"],
                    genres=genres,
                    predicted_rating=avg_r,
                    score=score,
                    reason=f"Recomendado com base nas avaliações de {u_count} usuário(s) com gostos afins"
                )
            )

        results.sort(key=lambda x: (x.score, x.predicted_rating), reverse=True)
        return results[:limit]

    def _fallback_genre(self, user_id: str, limit: int) -> List[RecommendationItem]:
        storage = neo4j_client.fallback_storage
        user_ratings = [r for r in storage.ratings if r["user_id"] == user_id and r["rating"] >= 3.0]
        if not user_ratings:
            return []

        # Contabiliza gêneros favoritos
        genre_counts = {}
        for r in user_ratings:
            m_genres = [mg["genre_name"] for mg in storage.movie_genres if mg["movie_id"] == r["movie_id"]]
            for g in m_genres:
                genre_counts[g] = genre_counts.get(g, 0) + 1

        if not genre_counts:
            return []

        fav_genres = sorted(genre_counts.keys(), key=lambda g: genre_counts[g], reverse=True)[:3]
        seen_movies = self._get_watched_or_rated_ids(user_id)

        results = []
        for m_id, m in storage.movies.items():
            if m_id in seen_movies:
                continue
            m_genres = [mg["genre_name"] for mg in storage.movie_genres if mg["movie_id"] == m_id]
            matched = [g for g in m_genres if g in fav_genres]
            if matched:
                ratings = [r["rating"] for r in storage.ratings if r["movie_id"] == m_id]
                avg_r = round(sum(ratings) / len(ratings), 2) if ratings else 4.0
                results.append(
                    RecommendationItem(
                        movie_id=m_id,
                        title=m["title"],
                        release_year=m["release_year"],
                        genres=m_genres,
                        predicted_rating=avg_r,
                        score=avg_r,
                        reason=f"Porque você tem afinidade com o gênero {matched[0]}"
                    )
                )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _fallback_trending(self, user_id: str, limit: int) -> List[RecommendationItem]:
        storage = neo4j_client.fallback_storage
        seen_movies = self._get_watched_or_rated_ids(user_id)

        results = []
        for m_id, m in storage.movies.items():
            if m_id in seen_movies:
                continue
            m_genres = [mg["genre_name"] for mg in storage.movie_genres if mg["movie_id"] == m_id]
            ratings = [r["rating"] for r in storage.ratings if r["movie_id"] == m_id]
            w_count = sum(1 for w in storage.watched if w["movie_id"] == m_id)
            r_count = len(ratings)
            avg_r = round(sum(ratings) / r_count, 2) if ratings else 4.0
            score = round(avg_r * 0.7 + (r_count + w_count) * 0.1, 2)
            results.append(
                RecommendationItem(
                    movie_id=m_id,
                    title=m["title"],
                    release_year=m["release_year"],
                    genres=m_genres,
                    predicted_rating=avg_r,
                    score=score,
                    reason="Destaque popular e bem avaliado no catálogo"
                )
            )

        results.sort(key=lambda x: (x.score, x.predicted_rating), reverse=True)
        return results[:limit]

recommendation_repo = RecommendationRepository()
