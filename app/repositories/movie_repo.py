import re
import uuid
from typing import List, Optional, Dict, Any
from app.database.neo4j_client import neo4j_client
from app.models.schemas import MovieCreate, MovieResponse, GenreResponse

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')

class MovieRepository:
    async def create_genre(self, name: str) -> GenreResponse:
        name_clean = name.strip()
        if neo4j_client.is_connected:
            query = """
            MERGE (g:Genre {name: $name})
            RETURN g.name AS name
            """
            await neo4j_client.run_write(query, {"name": name_clean})
            return GenreResponse(name=name_clean, movie_count=0)
        else:
            neo4j_client.fallback_storage.genres[name_clean] = {"name": name_clean}
            return GenreResponse(name=name_clean, movie_count=0)

    async def list_genres(self) -> List[GenreResponse]:
        if neo4j_client.is_connected:
            query = """
            MATCH (g:Genre)
            OPTIONAL MATCH (:Movie)-[r:BELONGS_TO]->(g)
            RETURN g.name AS name, count(r) AS movie_count
            ORDER BY g.name ASC
            """
            records = await neo4j_client.run_query(query)
            return [GenreResponse(name=row["name"], movie_count=row["movie_count"]) for row in records]
        else:
            storage = neo4j_client.fallback_storage
            result = []
            for g_name in storage.genres.keys():
                m_count = sum(1 for mg in storage.movie_genres if mg["genre_name"] == g_name)
                result.append(GenreResponse(name=g_name, movie_count=m_count))
            return sorted(result, key=lambda x: x.name)

    async def create_movie(self, movie_in: MovieCreate) -> MovieResponse:
        movie_id = movie_in.id or f"mov-{slugify(movie_in.title)[:20]}-{uuid.uuid4().hex[:4]}"
        genres_cleaned = [g.strip() for g in movie_in.genres if g.strip()]

        if neo4j_client.is_connected:
            query = """
            MERGE (m:Movie {id: $id})
            ON CREATE SET m.title = $title, m.release_year = $release_year
            WITH m
            UNWIND $genres AS gName
            MERGE (g:Genre {name: gName})
            MERGE (m)-[:BELONGS_TO]->(g)
            RETURN m.id AS id, m.title AS title, m.release_year AS release_year
            """
            await neo4j_client.run_write(query, {
                "id": movie_id,
                "title": movie_in.title,
                "release_year": movie_in.release_year,
                "genres": genres_cleaned
            })
            return MovieResponse(
                id=movie_id,
                title=movie_in.title,
                release_year=movie_in.release_year,
                genres=genres_cleaned,
                avg_rating=None,
                rating_count=0
            )
        else:
            storage = neo4j_client.fallback_storage
            storage.movies[movie_id] = {
                "id": movie_id,
                "title": movie_in.title,
                "release_year": movie_in.release_year
            }
            for g in genres_cleaned:
                storage.genres[g] = {"name": g}
                if not any(mg["movie_id"] == movie_id and mg["genre_name"] == g for mg in storage.movie_genres):
                    storage.movie_genres.append({"movie_id": movie_id, "genre_name": g})

            return MovieResponse(
                id=movie_id,
                title=movie_in.title,
                release_year=movie_in.release_year,
                genres=genres_cleaned,
                avg_rating=None,
                rating_count=0
            )

    async def get_movie_by_id(self, movie_id: str) -> Optional[MovieResponse]:
        if neo4j_client.is_connected:
            query = """
            MATCH (m:Movie {id: $id})
            OPTIONAL MATCH (m)-[:BELONGS_TO]->(g:Genre)
            OPTIONAL MATCH (:User)-[r:RATED]->(m)
            RETURN m.id AS id, m.title AS title, m.release_year AS release_year,
                   collect(DISTINCT g.name) AS genres,
                   round(avg(r.rating), 2) AS avg_rating,
                   count(r) AS rating_count
            """
            records = await neo4j_client.run_query(query, {"id": movie_id})
            if records:
                row = records[0]
                return MovieResponse(
                    id=row["id"],
                    title=row["title"],
                    release_year=row["release_year"],
                    genres=row["genres"] or [],
                    avg_rating=row["avg_rating"],
                    rating_count=row["rating_count"]
                )
            return None
        else:
            storage = neo4j_client.fallback_storage
            m = storage.movies.get(movie_id)
            if not m:
                return None
            genres = [mg["genre_name"] for mg in storage.movie_genres if mg["movie_id"] == movie_id]
            ratings = [r["rating"] for r in storage.ratings if r["movie_id"] == movie_id]
            avg_r = round(sum(ratings) / len(ratings), 2) if ratings else None
            return MovieResponse(
                id=m["id"],
                title=m["title"],
                release_year=m["release_year"],
                genres=genres,
                avg_rating=avg_r,
                rating_count=len(ratings)
            )

    async def list_movies(self) -> List[MovieResponse]:
        if neo4j_client.is_connected:
            query = """
            MATCH (m:Movie)
            OPTIONAL MATCH (m)-[:BELONGS_TO]->(g:Genre)
            OPTIONAL MATCH (:User)-[r:RATED]->(m)
            RETURN m.id AS id, m.title AS title, m.release_year AS release_year,
                   collect(DISTINCT g.name) AS genres,
                   round(avg(r.rating), 2) AS avg_rating,
                   count(r) AS rating_count
            ORDER BY m.title ASC
            """
            records = await neo4j_client.run_query(query)
            return [
                MovieResponse(
                    id=row["id"],
                    title=row["title"],
                    release_year=row["release_year"],
                    genres=row["genres"] or [],
                    avg_rating=row["avg_rating"],
                    rating_count=row["rating_count"]
                )
                for row in records
            ]
        else:
            storage = neo4j_client.fallback_storage
            result = []
            for m in storage.movies.values():
                genres = [mg["genre_name"] for mg in storage.movie_genres if mg["movie_id"] == m["id"]]
                ratings = [r["rating"] for r in storage.ratings if r["movie_id"] == m["id"]]
                avg_r = round(sum(ratings) / len(ratings), 2) if ratings else None
                result.append(MovieResponse(
                    id=m["id"],
                    title=m["title"],
                    release_year=m["release_year"],
                    genres=genres,
                    avg_rating=avg_r,
                    rating_count=len(ratings)
                ))
            return sorted(result, key=lambda x: x.title)

movie_repo = MovieRepository()
