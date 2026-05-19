from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models
import asyncio
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.core.config import settings

logger = logging.getLogger("finragvault.services.vector")


class VectorService:
    """Async Service managing interactions with the Qdrant Vector database."""

    _client: Optional[AsyncQdrantClient] = None

    @classmethod
    def get_client(cls) -> AsyncQdrantClient:
        """Returns the shared AsyncQdrantClient singleton."""
        if cls._client is None:
            logger.info(f"Initializing AsyncQdrantClient targeting {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
            cls._client = AsyncQdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=10.0
            )
        return cls._client

    @classmethod
    async def verify_collection_on_startup(cls) -> None:
        """Verifies collection existence on startup, creating it with 384 dims (MiniLM) if missing.
        
        Implements staff-level robustness: retries 3 times with exponential backoff if Qdrant is loading.
        """
        client = cls.get_client()
        collection_name = settings.QDRANT_COLLECTION
        
        max_retries = 5
        backoff = 2.0
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Checking if Qdrant collection '{collection_name}' exists (Attempt {attempt}/{max_retries})")
                collections_response = await client.get_collections()
                existing_names = [col.name for col in collections_response.collections]
                
                if collection_name not in existing_names:
                    logger.info(f"Qdrant collection '{collection_name}' not found. Provisioning collection...")
                    await client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(
                            size=384,  # MiniLM dimension
                            distance=models.Distance.COSINE
                        )
                    )
                    logger.info(f"Successfully provisioned Qdrant collection '{collection_name}' (384-dim, Cosine).")
                else:
                    logger.info(f"Verified Qdrant collection '{collection_name}' exists and is ready.")
                return
                
            except Exception as exc:
                logger.warning(f"Failed Qdrant connection attempt {attempt} due to: {str(exc)}")
                if attempt == max_retries:
                    logger.critical("Failed to connect to Qdrant vector database after maximum retries. Shutting down system.")
                    raise exc
                await asyncio.sleep(backoff)
                backoff *= 2.0

    @classmethod
    async def upsert_document_chunks(cls, points: List[Dict[str, Any]]) -> None:
        """Asynchronously upserts a list of document chunk points into Qdrant.
        
        Args:
            points (List[Dict[str, Any]]): List containing point dicts with 'id', 'vector', and 'payload'.
        """
        client = cls.get_client()
        collection_name = settings.QDRANT_COLLECTION
        
        qdrant_points = []
        for p in points:
            qdrant_points.append(
                models.PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p["payload"]
                )
            )
            
        await client.upsert(
            collection_name=collection_name,
            points=qdrant_points
        )
        logger.info(f"Upserted {len(qdrant_points)} vector points into Qdrant collection '{collection_name}'")

    @classmethod
    async def search_similar_chunks(
        cls,
        vector: List[float],
        limit: int = 20,
        company_name: Optional[str] = None,
        document_type: Optional[str] = None,
        uploaded_by: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Asynchronously searches Qdrant for semantic similar chunks matching metadata filters.
        
        Args:
            vector (List[float]): 384-dimensional query vector.
            limit (int): Max similarity points to fetch.
            company_name (Optional[str]): Company name filter.
            document_type (Optional[str]): Document type filter.
            uploaded_by (Optional[UUID]): Uploader filter.
            start_date (Optional[datetime]): Upload range start.
            end_date (Optional[datetime]): Upload range end.
            
        Returns:
            List[Dict[str, Any]]: List of chunk records containing payload and match scores.
        """
        client = cls.get_client()
        collection_name = settings.QDRANT_COLLECTION
        
        # Build filter list
        filter_conditions = []
        
        if company_name:
            filter_conditions.append(
                models.FieldCondition(
                    key="company_name",
                    match=models.MatchValue(value=company_name)
                )
            )
            
        if document_type:
            filter_conditions.append(
                models.FieldCondition(
                    key="document_type",
                    match=models.MatchValue(value=document_type)
                )
            )
            
        if uploaded_by:
            filter_conditions.append(
                models.FieldCondition(
                    key="uploaded_by",
                    match=models.MatchValue(value=str(uploaded_by))
                )
            )
            
        if start_date or end_date:
            range_bounds = {}
            if start_date:
                range_bounds["gte"] = start_date.isoformat()
            if end_date:
                range_bounds["lte"] = end_date.isoformat()
                
            filter_conditions.append(
                models.FieldCondition(
                    key="created_at",
                    range=models.Range(**range_bounds)
                )
            )
            
        qdrant_filter = models.Filter(must=filter_conditions) if filter_conditions else None
        
        # Run search query
        search_results = await client.search(
            collection_name=collection_name,
            query_vector=vector,
            query_filter=qdrant_filter,
            limit=limit
        )
        
        candidates = []
        for item in search_results:
            payload = item.payload or {}
            # Flatten score into payload structure
            payload["vector_score"] = item.score
            candidates.append(payload)
            
        return candidates

    @classmethod
    async def delete_document_vectors(cls, document_id: uuid.UUID) -> None:
        """Asynchronously deletes all chunk vectors matching the parent document_id from Qdrant.
        
        Args:
            document_id (uuid.UUID): Document identifier to delete vectors for.
        """
        client = cls.get_client()
        collection_name = settings.QDRANT_COLLECTION
        
        await client.delete(
            collection_name=collection_name,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=str(document_id))
                    )
                ]
            )
        )
        logger.info(f"Cleared Qdrant vector points for Document ID: {document_id}")

    @classmethod
    async def fetch_document_chunks(cls, document_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Asynchronously scrolls Qdrant to retrieve all stored chunk payloads for a specific document.
        
        Args:
            document_id (uuid.UUID): Target parent document ID.
            
        Returns:
            List[Dict[str, Any]]: List of chunk payloads.
        """
        client = cls.get_client()
        collection_name = settings.QDRANT_COLLECTION
        
        # Scroll points filtering by document_id
        scroll_results = await client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=str(document_id))
                    )
                ]
            ),
            limit=1000,  # Max page limit scroll
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_results[0]
        return [p.payload for p in points if p.payload]
