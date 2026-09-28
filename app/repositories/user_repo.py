import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.database.neo4j_client import neo4j_client
from app.models.schemas import UserCreate, UserResponse, UserDetailResponse, WatchedResponse, RatingResponse

def get_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class UserRepository:
    async def create_user(self, user_in: UserCreate) -> UserResponse:
        user_id = user_in.id or f"user-{uuid.uuid4().hex[:8]}"
        created_at = get_utc_iso()
        
        if neo4j_client.is_connected:
            query = """
            MERGE (u:User {id: $id})
            ON CREATE SET u.name = $name, u.email = $email, u.created_at = $created_at
            RETURN u.id AS id, u.name AS name, u.email AS email, u.created_at AS created_at
            """
            params = {
                "id": user_id,
                "name": user_in.name,
                "email": user_in.email,
                "created_at": created_at
            }
            records = await neo4j_client.run_write(query, params)
            if records:
                row = records[0]
                return UserResponse(
                    id=row["id"],
                    name=row["name"],
                    email=row["email"],
                    created_at=row["created_at"],
                    watched_count=0,
                    ratings_count=0
                )
        else:
            # Fallback em memória
            neo4j_client.fallback_storage.users[user_id] = {
                "id": user_id,
                "name": user_in.name,
                "email": user_in.email,
                "created_at": created_at
            }
            return UserResponse(
                id=user_id,
                name=user_in.name,
                email=user_in.email,
                created_at=created_at,
                watched_count=0,
                ratings_count=0
            )

    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        if neo4j_client.is_connected:
            query = """
            MATCH (u:User {id: $id})
            OPTIONAL MATCH (u)-[w:WATCHED]->(:Movie)
            OPTIONAL MATCH (u)-[r:RATED]->(:Movie)
            RETURN u.id AS id, u.name AS name, u.email AS email, u.created_at AS created_at,
                   count(DISTINCT w) AS watched_count, count(DISTINCT r) AS ratings_count
            """
            records = await neo4j_client.run_query(query, {"id": user_id})
            if records:
                row = records[0]
                return UserResponse(
                    id=row["id"],
                    name=row["name"],
                    email=row["email"],
                    created_at=row["created_at"],
                    watched_count=row["watched_count"],
                    ratings_count=row["ratings_count"]
                )
            return None
        else:
            storage = neo4j_client.fallback_storage
            user = storage.users.get(user_id)
            if not user:
                return None
            w_count = sum(1 for w in storage.watched if w["user_id"] == user_id)
            r_count = sum(1 for r in storage.ratings if r["user_id"] == user_id)
            return UserResponse(
                id=user["id"],
                name=user["name"],
                email=user["email"],
                created_at=user["created_at"],
                watched_count=w_count,
                ratings_count=r_count
            )

    async def list_users(self) -> List[UserResponse]:
        if neo4j_client.is_connected:
            query = """
            MATCH (u:User)
            OPTIONAL MATCH (u)-[w:WATCHED]->(:Movie)
            OPTIONAL MATCH (u)-[r:RATED]->(:Movie)
            RETURN u.id AS id, u.name AS name, u.email AS email, u.created_at AS created_at,
                   count(DISTINCT w) AS watched_count, count(DISTINCT r) AS ratings_count
            ORDER BY u.name ASC
            """
            records = await neo4j_client.run_query(query)
            return [
                UserResponse(
                    id=row["id"],
                    name=row["name"],
                    email=row["email"],
                    created_at=row["created_at"],
                    watched_count=row["watched_count"],
                    ratings_count=row["ratings_count"]
                )
                for row in records
            ]
        else:
            storage = neo4j_client.fallback_storage
            result = []
            for u in storage.users.values():
                w_count = sum(1 for w in storage.watched if w["user_id"] == u["id"])
                r_count = sum(1 for r in storage.ratings if r["user_id"] == u["id"])
                result.append(
                    UserResponse(
                        id=u["id"],
                        name=u["name"],
                        email=u["email"],
                        created_at=u["created_at"],
                        watched_count=w_count,
                        ratings_count=r_count
                    )
                )
            return sorted(result, key=lambda x: x.name)

    async def get_user_details(self, user_id: str) -> Optional[UserDetailResponse]:
        base_user = await self.get_user_by_id(user_id)
        if not base_user:
            return None

        watched_items = []
        rating_items = []

        if neo4j_client.is_connected:
            watched_query = """
            MATCH (u:User {id: $id})-[w:WATCHED]->(m:Movie)
            OPTIONAL MATCH (m)-[:BELONGS_TO]->(g:Genre)
            RETURN m.id AS movie_id, m.title AS title, m.release_year AS release_year,
                   collect(DISTINCT g.name) AS genres, w.watched_at AS watched_at
            ORDER BY w.watched_at DESC
            """
            w_records = await neo4j_client.run_query(watched_query, {"id": user_id})
            for row in w_records:
                watched_items.append({
                    "movie_id": row["movie_id"],
                    "title": row["title"],
                    "release_year": row["release_year"],
                    "genres": row["genres"] or [],
                    "watched_at": row["watched_at"]
                })

            ratings_query = """
            MATCH (u:User {id: $id})-[r:RATED]->(m:Movie)
            RETURN m.id AS movie_id, m.title AS title, r.rating AS rating,
                   r.comment AS comment, r.rated_at AS rated_at
            ORDER BY r.rated_at DESC
            """
            r_records = await neo4j_client.run_query(ratings_query, {"id": user_id})
            for row in r_records:
                rating_items.append({
                    "movie_id": row["movie_id"],
                    "title": row["title"],
                    "rating": float(row["rating"]),
                    "comment": row["comment"],
                    "rated_at": row["rated_at"]
                })
        else:
            storage = neo4j_client.fallback_storage
            for w in storage.watched:
                if w["user_id"] == user_id:
                    m = storage.movies.get(w["movie_id"], {})
                    genres = [mg["genre_name"] for mg in storage.movie_genres if mg["movie_id"] == w["movie_id"]]
                    watched_items.append({
                        "movie_id": w["movie_id"],
                        "title": m.get("title", w["movie_id"]),
                        "release_year": m.get("release_year"),
                        "genres": genres,
                        "watched_at": w["watched_at"]
                    })
            for r in storage.ratings:
                if r["user_id"] == user_id:
                    m = storage.movies.get(r["movie_id"], {})
                    rating_items.append({
                        "movie_id": r["movie_id"],
                        "title": m.get("title", r["movie_id"]),
                        "rating": float(r["rating"]),
                        "comment": r.get("comment"),
                        "rated_at": r["rated_at"]
                    })

        return UserDetailResponse(
            id=base_user.id,
            name=base_user.name,
            email=base_user.email,
            created_at=base_user.created_at,
            watched_count=len(watched_items),
            ratings_count=len(rating_items),
            watched_movies=watched_items,
            ratings=rating_items
        )

    async def record_watched(self, user_id: str, movie_id: str, watched_at: Optional[str] = None) -> WatchedResponse:
        ts = watched_at or get_utc_iso()
        movie_title = movie_id

        if neo4j_client.is_connected:
            query = """
            MATCH (u:User {id: $user_id})
            MATCH (m:Movie {id: $movie_id})
            MERGE (u)-[w:WATCHED]->(m)
            SET w.watched_at = $watched_at
            RETURN u.id AS user_id, m.id AS movie_id, m.title AS movie_title, w.watched_at AS watched_at
            """
            records = await neo4j_client.run_write(query, {
                "user_id": user_id,
                "movie_id": movie_id,
                "watched_at": ts
            })
            if records:
                movie_title = records[0]["movie_title"]
        else:
            storage = neo4j_client.fallback_storage
            existing = next((w for w in storage.watched if w["user_id"] == user_id and w["movie_id"] == movie_id), None)
            if existing:
                existing["watched_at"] = ts
            else:
                storage.watched.append({
                    "user_id": user_id,
                    "movie_id": movie_id,
                    "watched_at": ts
                })
            m = storage.movies.get(movie_id)
            if m:
                movie_title = m["title"]

        return WatchedResponse(
            user_id=user_id,
            movie_id=movie_id,
            movie_title=movie_title,
            watched_at=ts,
            cache_invalidated=True
        )

    async def record_rating(
        self,
        user_id: str,
        movie_id: str,
        rating: float,
        comment: Optional[str] = None,
        rated_at: Optional[str] = None
    ) -> RatingResponse:
        ts = rated_at or get_utc_iso()
        movie_title = movie_id

        if neo4j_client.is_connected:
            query = """
            MATCH (u:User {id: $user_id})
            MATCH (m:Movie {id: $movie_id})
            MERGE (u)-[r:RATED]->(m)
            SET r.rating = $rating, r.comment = $comment, r.rated_at = $rated_at
            RETURN u.id AS user_id, m.id AS movie_id, m.title AS movie_title,
                   r.rating AS rating, r.comment AS comment, r.rated_at AS rated_at
            """
            records = await neo4j_client.run_write(query, {
                "user_id": user_id,
                "movie_id": movie_id,
                "rating": rating,
                "comment": comment or "",
                "rated_at": ts
            })
            if records:
                movie_title = records[0]["movie_title"]
        else:
            storage = neo4j_client.fallback_storage
            existing = next((r for r in storage.ratings if r["user_id"] == user_id and r["movie_id"] == movie_id), None)
            if existing:
                existing["rating"] = rating
                existing["comment"] = comment
                existing["rated_at"] = ts
            else:
                storage.ratings.append({
                    "user_id": user_id,
                    "movie_id": movie_id,
                    "rating": rating,
                    "comment": comment,
                    "rated_at": ts
                })
            m = storage.movies.get(movie_id)
            if m:
                movie_title = m["title"]

        return RatingResponse(
            user_id=user_id,
            movie_id=movie_id,
            movie_title=movie_title,
            rating=rating,
            comment=comment,
            rated_at=ts,
            cache_invalidated=True
        )

user_repo = UserRepository()
