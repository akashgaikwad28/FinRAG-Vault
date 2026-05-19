from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.document import Document
from app.schemas.document import DocumentUpdate
from typing import List, Optional, Tuple
import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger("finragvault.repositories.document")


class DocumentRepository:
    """Asynchronous Repository handling relational DB operations for the Document entity."""

    @staticmethod
    async def get_by_id(session: AsyncSession, doc_id: uuid.UUID) -> Optional[Document]:
        """Fetches an active Document record by UUID, ignoring soft deleted entities."""
        query = select(Document).where(and_(Document.id == doc_id, Document.deleted_at.is_(None)))
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        title: str,
        filename: str,
        company_name: str,
        document_type: str,
        uploaded_by: uuid.UUID,
        storage_path: str
    ) -> Document:
        """Constructs and persists a new Document metadata entry in processing status."""
        doc = Document(
            title=title,
            filename=filename,
            company_name=company_name,
            document_type=document_type,
            uploaded_by=uploaded_by,
            storage_path=storage_path,
            status="processing"
        )
        session.add(doc)
        await session.flush()
        logger.info(f"Created Document record: '{title}' (ID: {doc.id}, Status: {doc.status})")
        return doc

    @staticmethod
    async def list_documents(
        session: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        company_name: Optional[str] = None,
        document_type: Optional[str] = None,
        uploaded_by: Optional[uuid.UUID] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Document], int]:
        """Queries a paginated and filtered list of active documents, returns (items, total_count)."""
        skip = (page - 1) * page_size
        
        # Build query filters
        filters = [Document.deleted_at.is_(None)]
        if company_name:
            filters.append(Document.company_name == company_name)
        if document_type:
            filters.append(Document.document_type == document_type)
        if uploaded_by:
            filters.append(Document.uploaded_by == uploaded_by)
            
        # Build query
        query = select(Document).where(and_(*filters))
        
        # Add sorting
        sort_column = getattr(Document, sort_by, Document.created_at)
        if sort_order.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
            
        # Execute count query
        count_query = select(func.count(Document.id)).where(and_(*filters))
        count_result = await session.execute(count_query)
        total = count_result.scalar_one()
        
        # Execute list query
        query = query.offset(skip).limit(page_size)
        result = await session.execute(query)
        docs = list(result.scalars().all())
        
        return docs, total

    @staticmethod
    async def update(session: AsyncSession, doc: Document, updates: DocumentUpdate) -> Document:
        """Applies ingestion lifecycle changes or title modifications to the Document."""
        if updates.title is not None:
            doc.title = updates.title
        if updates.status is not None:
            doc.status = updates.status
        if updates.error_message is not None:
            doc.error_message = updates.error_message
            
        session.add(doc)
        await session.flush()
        logger.info(f"Updated Document status: '{doc.title}' (ID: {doc.id}, Status: {doc.status})")
        return doc

    @staticmethod
    async def soft_delete(session: AsyncSession, doc: Document) -> None:
        """Applies a soft-delete timestamp to a Document record."""
        doc.deleted_at = datetime.now(timezone.utc)
        session.add(doc)
        await session.flush()
        logger.info(f"Soft deleted Document record: '{doc.title}' (ID: {doc.id})")
