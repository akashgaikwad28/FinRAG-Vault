from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import Optional

from app.api.deps.deps import get_db, get_current_user, require_permissions
from app.schemas.auth import StandardResponse
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from app.models.user import User
from app.utils.constants import Permission, SystemRole
from app.core.exceptions import PermissionDenied
from app.api.routes.auth import record_audit_log

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=StandardResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a new financial document",
    description="Streams the file in chunked blocks to disk, saves database metadata, and kicks off an asynchronous background task to extract, split, embed, and index text in Qdrant."
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Target file (PDF, DOCX, TXT)"),
    title: str = Form(..., min_length=2, max_length=255, description="Document title descriptor"),
    company_name: str = Form(..., min_length=1, max_length=100, description="Company represented by document"),
    document_type: str = Form(..., description="Document type: 'invoice', 'report', 'contract'"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions([Permission.DOCUMENT_UPLOAD]))
) -> StandardResponse:
    # 1. Enforce Client block: Clients are strictly forbidden from uploading files
    user_roles = [r.name for r in current_user.roles]
    if SystemRole.CLIENT.value in user_roles:
        raise PermissionDenied("Clients are not authorized to upload documents")
        
    # 2. Run upload and DB creation in a transaction
    async with session.begin():
        doc = await DocumentService.upload_document(
            session=session,
            file=file,
            title=title,
            company_name=company_name,
            document_type=document_type,
            uploaded_by=current_user.id,
            background_tasks=background_tasks
        )
        # Record upload in audit logs
        await record_audit_log(session, f"document_upload: {doc.title} (ID: {doc.id})", current_user.id)
        
    doc_data = DocumentResponse.model_validate(doc)
    return StandardResponse(
        success=True,
        message="Document uploaded successfully. Background processing started.",
        data=doc_data
    )


@router.get(
    "",
    response_model=StandardResponse,
    summary="List all documents",
    description="Queries a paginated, sorted, and filtered list of active documents. Enforces absolute company-level isolation for Client users."
)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    company: Optional[str] = Query(None, description="Filter by company (overridden for Client role)"),
    doc_type: Optional[str] = Query(None, description="Filter by category ('invoice', 'report', 'contract')"),
    uploaded_by: Optional[uuid.UUID] = Query(None, description="Filter by uploader UUID"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order ('asc', 'desc')"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions([Permission.DOCUMENT_READ]))
) -> StandardResponse:
    user_roles = [r.name for r in current_user.roles]
    
    # CRITICAL SECURITY RULE: Client isolation override
    # If the user is a Client, force they can only list documents belonging to their designated company
    if SystemRole.CLIENT.value in user_roles:
        company = current_user.company_name
        if not company:
            raise PermissionDenied("Client account is not assigned to any company boundary")
            
    docs, total = await DocumentService.list_documents(
        session=session,
        page=page,
        page_size=page_size,
        company_name=company,
        document_type=doc_type,
        uploaded_by=uploaded_by,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total_pages = (total + page_size - 1) // page_size
    doc_schemas = [DocumentResponse.model_validate(d) for d in docs]
    
    return StandardResponse(
        success=True,
        message="Documents listed successfully",
        data={
            "items": doc_schemas,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    )


@router.get(
    "/{document_id}",
    response_model=StandardResponse,
    summary="Get document details by ID",
    description="Returns metadata detail for a specific Document record. Enforces absolute multi-tenant company bounds checking."
)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions([Permission.DOCUMENT_READ]))
) -> StandardResponse:
    doc = await DocumentService.get_document_by_id(session, document_id)
    
    # CRITICAL SECURITY RULE: Client multi-tenant isolation guard
    user_roles = [r.name for r in current_user.roles]
    if SystemRole.CLIENT.value in user_roles:
        if doc.company_name != current_user.company_name:
            raise PermissionDenied("Forbidden: You are not authorized to access documents from other companies")
            
    doc_data = DocumentResponse.model_validate(doc)
    return StandardResponse(
        success=True,
        message="Document details retrieved",
        data=doc_data
    )


@router.delete(
    "/{document_id}",
    response_model=StandardResponse,
    summary="Delete a document",
    description="Deletes local files, clears vector embeddings from Qdrant, and soft-deletes DB metadata."
)
async def delete_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permissions([Permission.DOCUMENT_DELETE]))
) -> StandardResponse:
    # Eagerly retrieve the document metadata to verify roles & log action details
    doc = await DocumentService.get_document_by_id(session, document_id)
    
    # CRITICAL SECURITY RULE: Client accounts cannot delete documents
    user_roles = [r.name for r in current_user.roles]
    if SystemRole.CLIENT.value in user_roles:
        raise PermissionDenied("Clients are not authorized to delete documents")
        
    async with session.begin():
        await DocumentService.delete_document(session, document_id)
        await record_audit_log(session, f"document_delete: {doc.title} (ID: {doc.id})", current_user.id)
        
    return StandardResponse(
        success=True,
        message=f"Document '{doc.title}' and associated embeddings successfully deleted.",
        data=None
    )
