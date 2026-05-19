from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile, BackgroundTasks
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.core.exceptions import EntityNotFound, FileValidationError, FinRAGException
from app.repositories.document_repository import DocumentRepository
from app.models.document import Document
from app.schemas.document import DocumentUpdate, DocumentResponse
from app.utils.file_utils import sanitize_filename, validate_file_metadata, save_upload_file_chunked
from app.services.parser_service import ParserService
from app.core.database import AsyncSessionLocal

logger = logging.getLogger("finragvault.services.document")


async def _run_background_ingestion(
    doc_id: uuid.UUID,
    file_path: str,
    extension: str,
    uploaded_by: uuid.UUID
) -> None:
    """Decoupled background task executing file parsing, semantic chunking, and Qdrant indexing.
    
    Loads its own isolated DB session to prevent transaction leakages across long-running background tasks.
    """
    logger.info(f"Starting background semantic ingestion for Document ID: {doc_id}")
    
    # Import RAG service lazily to avoid circular dependencies
    from app.services.rag_service import RagService
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch the target document record
            doc = await DocumentRepository.get_by_id(session, doc_id)
            if not doc:
                logger.error(f"Background ingestion failed: Document {doc_id} not found in DB")
                return
                
            # 2. Extract full text from file
            text = await ParserService.parse_document_async(file_path, extension)
            if not text or not text.strip():
                raise ValueError("The document contains no parseable text or empty pages.")
                
            # 3. Call RAG indexing pipeline
            await RagService.index_document(session, doc, text)
            
            # 4. Update status to indexed
            async with session.begin():
                await DocumentRepository.update(
                    session=session,
                    doc=doc,
                    updates=DocumentUpdate(status="indexed", error_message=None)
                )
            logger.info(f"Background ingestion completed successfully for Document ID: {doc_id}")
            
        except Exception as exc:
            logger.error(f"Background ingestion failed for Document ID {doc_id}: {str(exc)}", exc_info=True)
            try:
                # Reload session to ensure active transaction for error recording
                async with AsyncSessionLocal() as err_session:
                    async with err_session.begin():
                        error_doc = await DocumentRepository.get_by_id(err_session, doc_id)
                        if error_doc:
                            await DocumentRepository.update(
                                session=err_session,
                                doc=error_doc,
                                updates=DocumentUpdate(
                                    status="failed",
                                    error_message=str(exc)[:1000]  # Cap length
                                )
                            )
            except Exception as nested_exc:
                logger.critical(f"Failed to save error status for Document {doc_id}: {str(nested_exc)}")


class DocumentService:
    """Orchestrator for Document uploads, details, pagination, and system deletions."""

    @staticmethod
    async def upload_document(
        session: AsyncSession,
        file: UploadFile,
        title: str,
        company_name: str,
        document_type: str,
        uploaded_by: uuid.UUID,
        background_tasks: BackgroundTasks
    ) -> Document:
        """Streams upload file to local disk, saves DB record, and enqueues the RAG indexing task."""
        # 1. Validate extension and MIME types
        validate_file_metadata(file)
        
        # 2. Sanitize output file name
        original_name = file.filename or "unknown_file"
        sanitized_name = sanitize_filename(original_name)
        
        # 3. Formulate local disk storage path
        unique_id = uuid.uuid4()
        extension = sanitized_name.split(".")[-1].lower() if "." in sanitized_name else "txt"
        disk_filename = f"{unique_id}_{sanitized_name}"
        local_path = os.path.join(settings.UPLOAD_DIR, disk_filename)
        
        # 4. Stream file in memory-safe chunks
        await save_upload_file_chunked(file, local_path)
        
        # 5. Create SQL record inside transaction
        doc = await DocumentRepository.create(
            session=session,
            title=title,
            filename=sanitized_name,
            company_name=company_name,
            document_type=document_type,
            uploaded_by=uploaded_by,
            storage_path=local_path
        )
        
        # 6. Enqueue RAG pipeline background execution
        background_tasks.add_task(
            _run_background_ingestion,
            doc_id=doc.id,
            file_path=local_path,
            extension=extension,
            uploaded_by=uploaded_by
        )
        
        return doc

    @staticmethod
    async def get_document_by_id(session: AsyncSession, doc_id: uuid.UUID) -> Document:
        """Fetches document metadata by UUID, raising EntityNotFound if not found."""
        doc = await DocumentRepository.get_by_id(session, doc_id)
        if not doc:
            raise EntityNotFound(f"Document with ID '{doc_id}' not found")
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
    ) -> tuple[list[Document], int]:
        """Queries paginated documents with filtering criteria."""
        valid_sort_fields = ["created_at", "title", "company_name", "document_type", "status"]
        if sort_by not in valid_sort_fields:
            sort_by = "created_at"
            
        return await DocumentRepository.list_documents(
            session=session,
            page=page,
            page_size=page_size,
            company_name=company_name,
            document_type=document_type,
            uploaded_by=uploaded_by,
            sort_by=sort_by,
            sort_order=sort_order
        )

    @staticmethod
    async def delete_document(session: AsyncSession, doc_id: uuid.UUID) -> None:
        """Performs file cleanup, Qdrant deletion, and soft deletes DB record."""
        doc = await DocumentService.get_document_by_id(session, doc_id)
        
        # Import services lazily
        from app.services.vector_service import VectorService
        
        # 1. Attempt local file removal on disk
        if os.path.exists(doc.storage_path):
            try:
                os.remove(doc.storage_path)
                logger.info(f"Removed local document file from disk: {doc.storage_path}")
            except Exception as e:
                logger.error(f"Failed to delete local file '{doc.storage_path}': {str(e)}")
                
        # 2. Attempt Qdrant Vector database payload clearing
        try:
            await VectorService.delete_document_vectors(doc_id)
            logger.info(f"Cleared vector embeddings for Document ID: {doc_id}")
        except Exception as e:
            # Record error but do not block SQL operations
            logger.error(f"Failed to clear Qdrant vectors for Document ID {doc_id}: {str(e)}")
            
        # 3. Soft-delete database metadata record
        await DocumentRepository.soft_delete(session, doc)
