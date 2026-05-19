from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import uuid
import logging
from datetime import datetime, timezone

from app.models.document import Document
from app.models.user import User
from app.utils.constants import SystemRole
from app.core.exceptions import PermissionDenied
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.rerank_service import RerankService
from app.services.vector_service import VectorService

logger = logging.getLogger("finragvault.services.rag")


class RagService:
    """Core RAG pipeline service managing semantic document indexing and contextual searches."""

    @staticmethod
    async def index_document(session: AsyncSession, doc: Document, text: str) -> None:
        """Runs the semantic ingestion flow: chunking, embedding generation, and Qdrant upserts."""
        # 1. Chunking text using recursive characters splitter
        chunks = ChunkingService.split_text(text)
        if not chunks:
            logger.warning(f"No parseable text chunks generated for document: {doc.title} (ID: {doc.id})")
            return
            
        # 2. Generate vector embeddings for all chunks in batch
        embeddings = await EmbeddingService.generate_embeddings_async(chunks)
        
        # 3. Assemble point payloads for Qdrant storage
        chunk_points = []
        for idx, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc.id}_chunk_{idx}"))
            payload = {
                "document_id": str(doc.id),
                "chunk_id": chunk_id,
                "chunk_text": chunk_text,
                "company_name": doc.company_name,
                "document_type": doc.document_type,
                "uploaded_by": str(doc.uploaded_by),
                "created_at": doc.created_at.isoformat() if isinstance(doc.created_at, datetime) else datetime.now(timezone.utc).isoformat(),
                "chunk_index": idx,
                "title": doc.title
            }
            chunk_points.append({
                "id": chunk_id,
                "vector": embeddings[idx],
                "payload": payload
            })
            
        # 4. Save points to Qdrant vector database
        await VectorService.upsert_document_chunks(chunk_points)
        logger.info(f"Indexed {len(chunk_points)} semantic chunks into Qdrant for document ID: {doc.id}")

    @staticmethod
    def _apply_diversity_deduplication(
        reranked_chunks: List[Dict[str, Any]],
        top_k: int = 5,
        max_chunks_per_document: int = 2
    ) -> List[Dict[str, Any]]:
        """Filters highly ranked candidates to guarantee multi-document context diversity.
        
        Avoids saturating the search window with consecutive chunks from a single document.
        """
        selected_list = []
        document_counts = {}
        backfill_list = []
        
        for chunk in reranked_chunks:
            doc_id = chunk["document_id"]
            count = document_counts.get(doc_id, 0)
            
            if count < max_chunks_per_document:
                selected_list.append(chunk)
                document_counts[doc_id] = count + 1
            else:
                backfill_list.append(chunk)
                
        # If diversity filtering dropped items and we are below top_k, fill up from backfill
        if len(selected_list) < top_k:
            fill_slots = top_k - len(selected_list)
            selected_list.extend(backfill_list[:fill_slots])
            
        return selected_list[:top_k]

    @staticmethod
    async def search_rag(
        session: AsyncSession,
        query: str,
        current_user: User,
        company_filter: Optional[str] = None,
        document_type_filter: Optional[str] = None,
        uploaded_by_filter: Optional[uuid.UUID] = None,
        start_date_filter: Optional[datetime] = None,
        end_date_filter: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Orchestrates query embedding, vector database filter matching, reranking, and deduplication.
        
        Enforces absolute company isolation boundaries for Client profiles.
        """
        user_roles = [role.name for role in current_user.roles]
        
        # CRITICAL SECURITY GATES: Enforce Client company bounds
        if SystemRole.CLIENT.value in user_roles:
            company_filter = current_user.company_name
            if not company_filter:
                raise PermissionDenied("Client user has no company boundaries defined")
                
        # 1. Generate Query Vector
        query_vector = await EmbeddingService.generate_query_embedding_async(query)
        
        # 2. Fetch top 20 candidate chunks from Qdrant with metadata filters
        candidates = await VectorService.search_similar_chunks(
            vector=query_vector,
            limit=20,
            company_name=company_filter,
            document_type=document_type_filter,
            uploaded_by=uploaded_by_filter,
            start_date=start_date_filter,
            end_date=end_date_filter
        )
        
        if not candidates:
            return []
            
        # 3. Enrich and verify candidate chunks from relational DB (filter deleted/failed ones)
        from app.repositories.rag_repository import RagRepository
        enriched = await RagRepository.enrich_and_verify_candidates(session, candidates)
        if not enriched:
            return []
            
        # 4. Cross-Encoder high-precision reranking
        reranked = await RerankService.rerank_candidates_async(
            query=query,
            candidates=enriched,
            top_k=20  # Maintain all for diversity sorting
        )
        
        # 4. Diversity Deduplication to extract top 5 rich blocks
        final_results = RagService._apply_diversity_deduplication(
            reranked_chunks=reranked,
            top_k=5,
            max_chunks_per_document=2
        )
        
        return final_results
