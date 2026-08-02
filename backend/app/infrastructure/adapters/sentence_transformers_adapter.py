import asyncio
from typing import List
from app.core.config import settings
from app.domain.ai.capabilities import IEmbeddingCapability

class SentenceTransformersEmbeddingAdapter(IEmbeddingCapability):
    def __init__(self, model_name: str = settings.EMBEDDING_MODEL_NAME) -> None:
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                self._model = "MOCK"
        return self._model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._embed_sync, texts)

    async def embed_query(self, query: str) -> List[float]:
        results = await self.embed_texts([query])
        return results[0]

    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        if model == "MOCK":
            # 384-dimensional mock embedding vector for testing fallback
            return [[0.01 * (i + 1) for i in range(384)] for _ in texts]
        embeddings = model.encode(texts, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]
