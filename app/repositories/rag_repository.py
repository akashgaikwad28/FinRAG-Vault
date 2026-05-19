from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.document import Document
from typing import List, Dict, Any, Set
import uuid
import logging

logger = logging.getLogger("finragvault.repositories.rag")


class RagRepository:
    """Coordinates and enriches vector database results with active SQL relational models."""

    @staticmethod
    async def enrich_and_verify_candidates(
        session: AsyncSession,
        candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Ensures that any candidates retrieved from Qdrant still exist and are active in PostgreSQL.
        
        Performs a batched SQL query to match and load document properties, filtering out chunks
        from soft-deleted or non-indexed documents.
        
        Args:
            session (AsyncSession): Active database session.
            candidates (List[Dict[str, Any]]): Unrefined chunk payload lists from Qdrant.
            
        Returns:
            List[Dict[str, Any]]: Refined and SQL-enriched chunk candidate list.
        """
        if not candidates:
            return []
            
        # 1. Gather all unique document UUIDs from candidates
        doc_ids: Set[uuid.UUID] = set()
        for c in candidates:
            try:
                doc_ids.add(uuid.UUID(c["document_id"]))
            except (ValueError, KeyError):
                pass
                
        if not doc_ids:
            return []
            
        # 2. Query relational Database for active, indexed documents in single batch
        query = select(Document).where(
            and_(
                Document.id.in_(doc_ids),
                Document.deleted_at.is_(None),
                Document.status == "indexed"
            )
        )
        result = await session.execute(query)
        active_docs = {doc.id: doc for doc in result.scalars().all()}
        
        # 3. Filter candidates and attach up-to-date document properties
        enriched_candidates = []
        for c in candidates:
            try:
                doc_uuid = uuid.UUID(c["document_id"])
                if doc_uuid in active_docs:
                    # Parent document is valid and active in SQL
                    doc = active_docs[doc_uuid]
                    
                    # Construct enriched candidate dictionary
                    enriched = c.copy()
                    enriched["title"] = doc.title
                    enriched["company_name"] = doc.company_name
                    enriched["document_type"] = doc.document_type
                    enriched["uploaded_by"] = str(doc.uploaded_by)
                    enriched_candidates.append(enriched)
            except (ValueError, KeyError):
                # Ignore malformed payloads
                pass
                
        logger.info(f"Relational enrichment filtered candidate list from {len(candidates)} down to {len(enriched_candidates)} valid SQL-backed chunks.")
        return enriched_candidates
