import os
from typing import Any, Dict, List, Optional
from app.core.config import settings

class EmbeddedQdrantVectorStoreAdapter:
    _shared_clients: Dict[str, Any] = {}

    def __init__(self, path: str = settings.QDRANT_PATH, collection_name: str = settings.QDRANT_COLLECTION) -> None:
        self.path = path
        self.collection_name = collection_name
        self._client = None
        self._init_qdrant()

    def _init_qdrant(self) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            os.makedirs(self.path, exist_ok=True)

            existing = self._shared_clients.get(self.path)
            if existing is not None:
                self._client = existing
                return

            try:
                client = QdrantClient(path=self.path)
            except Exception:
                # Disk storage lock conflict or path error — fallback to in-memory Qdrant client
                client = QdrantClient(location=":memory:")

            self._shared_clients[self.path] = client
            self._client = client

            collections = [c.name for c in self._client.get_collections().collections]
            if self.collection_name not in collections:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
        except ImportError:
            self._client = None

    async def upsert(self, ids: List[str], vectors: List[List[float]], payloads: List[Dict[str, Any]]) -> None:
        if not self._client:
            return
        from qdrant_client.models import PointStruct
        points = [
            PointStruct(id=idx, vector=vec, payload=pay)
            for idx, vec, pay in zip(ids, vectors, payloads)
        ]
        self._client.upsert(collection_name=self.collection_name, points=points)

    async def search(self, query_vector: List[float], limit: int = 5, filter_media_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._client:
            return []
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        query_filter = None
        if filter_media_id:
            query_filter = Filter(
                must=[FieldCondition(key="media_id", match=MatchValue(value=filter_media_id))]
            )

        results = self._client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=query_filter
        )
        return [
            {"id": str(hit.id), "score": hit.score, "payload": hit.payload}
            for hit in results.points
        ]
