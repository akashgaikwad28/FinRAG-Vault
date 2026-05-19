from sentence_transformers import CrossEncoder
import asyncio
import threading
from typing import List, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger("finragvault.services.rerank")


class RerankService:
    """Thread-safe Singleton service using Cross-Encoders to rerank vector similarity candidates."""

    _model: CrossEncoder = None
    _lock = threading.Lock()

    @classmethod
    def get_model(cls) -> CrossEncoder:
        """Loads and caches the Cross-Encoder model in a thread-safe singleton pattern."""
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    logger.info(f"Loading Cross-Encoder Reranker Model: {settings.RERANK_MODEL}")
                    cls._model = CrossEncoder(settings.RERANK_MODEL)
                    logger.info("Reranker Model loaded successfully.")
        return cls._model

    @classmethod
    async def rerank_candidates_async(
        cls,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Asynchronously computes rerank scores for candidate chunks, returning the top K results.
        
        Args:
            query (str): The search term query.
            candidates (List[Dict[str, Any]]): Unsorted list of retrieved chunks with a 'chunk_text' field.
            top_k (int): Number of final highest-scored candidates to return.
            
        Returns:
            List[Dict[str, Any]]: Re-ordered and sliced chunk dictionary list with attached cross-encoder score.
        """
        if not candidates:
            return []

        def _predict() -> List[Dict[str, Any]]:
            model = cls.get_model()
            
            # Formulate query-text pairs for cross-encoder inference
            pairs = [[query, item["chunk_text"]] for item in candidates]
            
            # Predict scores (higher = more relevant)
            scores = model.predict(pairs, convert_to_numpy=True, show_progress_bar=False)
            
            # Attach scores to the candidate dict blocks
            reranked = []
            for idx, score in enumerate(scores):
                candidate = candidates[idx].copy()
                candidate["score"] = float(score)
                reranked.append(candidate)
                
            # Sort descending based on cross-encoder output
            reranked.sort(key=lambda x: x["score"], reverse=True)
            return reranked[:top_k]

        return await asyncio.to_thread(_predict)
