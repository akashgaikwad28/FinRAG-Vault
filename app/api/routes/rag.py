from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List

from app.api.deps.deps import get_db, get_current_user, require_permissions
from app.schemas.auth import StandardResponse
from app.schemas.rag import RAGQueryRequest, RAGSearchResultItem, RAGContextResponse, RAGContextItem
from app.services.rag_service import RagService
from app.services.document_service import DocumentService
from app.services.vector_service import VectorService
from app.models.user import User
from app.utils.constants import Permission, SystemRole
from app.core.exceptions import PermissionDenied
from app.api.routes.auth import record_audit_log

router = APIRouter(prefix="/rag", tags=["RAG & Semantic Search"])


@router.post(
    "/search",
    response_model=StandardResponse,
    summary="Perform semantic hybrid search",
    description="Vector search with cross-encoder reranking and diversity filtering. Restricts Clients to their designated company boundary."
)
async def search_rag(
    payload: RAGQueryRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions([Permission.RAG_SEARCH]))
) -> StandardResponse:
    # 1. Coordinate search logic with filters
    results = await RagService.search_rag(
        session=session,
        query=payload.query,
        current_user=current_user,
        company_filter=payload.company_name,
        document_type_filter=payload.document_type,
        uploaded_by_filter=payload.uploaded_by,
        start_date_filter=payload.start_date,
        end_date_filter=payload.end_date
    )
    
    # 2. Map payload into standardized schemas
    search_results = []
    for item in results:
        search_results.append(
            RAGSearchResultItem(
                chunk_id=item["chunk_id"],
                chunk_text=item["chunk_text"],
                score=item["score"],
                document_id=uuid.UUID(item["document_id"]),
                title=item["title"],
                company_name=item["company_name"],
                document_type=item["document_type"],
                chunk_index=item["chunk_index"]
            )
        )
        
    # 3. Log audit event
    async with session.begin():
        await record_audit_log(session, f"semantic_search: {payload.query[:100]}", current_user.id)
        
    return StandardResponse(
        success=True,
        message="Semantic search executed successfully",
        data=search_results
    )


@router.post(
    "/index-document",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger manual document indexing",
    description="Extracts raw text, splits into character chunks, generates embeddings, and saves into Qdrant manually. Guarded by RAG_INDEX."
)
async def index_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions([Permission.RAG_INDEX]))
) -> StandardResponse:
    # Fetch active document record
    doc = await DocumentService.get_document_by_id(session, document_id)
    
    # Read text contents from disk
    from app.services.parser_service import ParserService
    extension = doc.filename.split(".")[-1].lower() if "." in doc.filename else "txt"
    
    text = await ParserService.parse_document_async(doc.storage_path, extension)
    if not text.strip():
        raise ValueError("Document file is empty or has no readable characters")
        
    # Trigger semantic pipeline indexing
    async with session.begin():
        await RagService.index_document(session, doc, text)
        
        # Update document status to indexed
        from app.schemas.document import DocumentUpdate
        await DocumentService.DocumentRepository.update(
            session=session,
            doc=doc,
            updates=DocumentUpdate(status="indexed", error_message=None)
        )
        await record_audit_log(session, f"manual_rag_index: {doc.title}", current_user.id)
        
    return StandardResponse(
        success=True,
        message=f"Document '{doc.title}' successfully indexed into Qdrant Vector database.",
        data=None
    )


@router.delete(
    "/remove-document/{document_id}",
    response_model=StandardResponse,
    summary="Remove vector embeddings from vector DB",
    description="Manually deletes all segment vectors for a document ID from Qdrant. Guarded by RAG_INDEX."
)
async def remove_document_vectors(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions([Permission.RAG_INDEX]))
) -> StandardResponse:
    doc = await DocumentService.get_document_by_id(session, document_id)
    
    # Trigger deletion in Qdrant
    await VectorService.delete_document_vectors(document_id)
    
    async with session.begin():
        # Update document status back to raw processing or failed
        from app.schemas.document import DocumentUpdate
        await DocumentService.DocumentRepository.update(
            session=session,
            doc=doc,
            updates=DocumentUpdate(status="processing", error_message="Vectors manually cleared")
        )
        await record_audit_log(session, f"manual_vector_clear: {doc.title}", current_user.id)
        
    return StandardResponse(
        success=True,
        message=f"Vector embeddings cleared from Qdrant for document ID: {document_id}",
        data=None
    )


@router.get(
    "/context/{document_id}",
    response_model=StandardResponse,
    summary="Retrieve all raw context chunks for a document",
    description="Retrieves a list of chunks stored in Qdrant representing the document. Enforces multi-tenant company boundaries."
)
async def get_document_context(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions([Permission.DOCUMENT_READ]))
) -> StandardResponse:
    # 1. Fetch document and verify permissions
    doc = await DocumentService.get_document_by_id(session, document_id)
    
    user_roles = [r.name for r in current_user.roles]
    if SystemRole.CLIENT.value in user_roles:
        if doc.company_name != current_user.company_name:
            raise PermissionDenied("Forbidden: You are not authorized to view this document's context")
            
    # 2. Retrieve point payloads directly from Qdrant
    chunks = await VectorService.fetch_document_chunks(document_id)
    
    # 3. Map into response models
    context_items = []
    for chunk in chunks:
        context_items.append(
            RAGContextItem(
                chunk_id=chunk["chunk_id"],
                chunk_text=chunk["chunk_text"],
                chunk_index=chunk["chunk_index"],
                created_at=chunk["created_at"]
            )
        )
        
    # Sort chunks by original character index order
    context_items.sort(key=lambda x: x.chunk_index)
    
    response = RAGContextResponse(
        document_id=document_id,
        title=doc.title,
        chunks=context_items
    )
    
    return StandardResponse(
        success=True,
        message="Document raw context retrieved successfully",
        data=response.model_dump()
    )
