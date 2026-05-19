from sentence_transformers import SentenceTransformer
import asyncio
import threading
from typing import List
from app.core.config import settings
import logging

logger = logging.getLogger("finragvault.services.embedding")


class EmbeddingService:
    """Thread-safe Singleton service generating sentence-transformer vector embeddings."""

    _model: SentenceTransformer = None
    _lock = threading.Lock()

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """Loads and caches the SentenceTransformer model in a thread-safe singleton pattern."""
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    logger.info(f"Loading Embedding Model: {settings.EMBEDDING_MODEL} (384 dimensions)")
                    # Load model onto CPU by default (or GPU if configured naturally by PyTorch)
                    cls._model = SentenceTransformer(settings.EMBEDDING_MODEL)
                    logger.info("Embedding Model loaded successfully.")
        return cls._model

    @classmethod
    async def generate_embeddings_async(cls, texts: List[str]) -> List[List[float]]:
        """Asynchronously generates standard float vector lists in batched threadpools.
        
        Args:
            texts (List[str]): Input list of text chunk strings.
            
        Returns:
            List[List[float]]: Batched list of 384-dimensional vector embeddings.
        """
        if not texts:
            return []

        def _encode() -> List[List[float]]:
            model = cls.get_model()
            # Generate numpy array vectors, then convert to standard Python float lists
            embeddings_np = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
            return embeddings_np.tolist()

        return await asyncio.to_thread(_encode)

    @classmethod
    async def generate_query_embedding_async(cls, query: str) -> List[float]:
        """Asynchronously encodes a single text query into a 384-dimensional vector embedding.
        
        Args:
            query (str): Input query text.
            
        Returns:
            List[float]: 384-dimensional vector embedding.
        """
        embeddings = await cls.generate_embeddings_async([query])
        if not embeddings:
            raise ValueError("Failed to generate vector embedding for search query")
        return embeddings[0]
