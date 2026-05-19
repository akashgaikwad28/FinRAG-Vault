from enum import Enum


class SystemRole(str, Enum):
    ADMIN = "Admin"
    ANALYST = "Financial Analyst"
    AUDITOR = "Auditor"
    CLIENT = "Client"


class DocumentType(str, Enum):
    INVOICE = "invoice"
    REPORT = "report"
    CONTRACT = "contract"


class IngestionStatus(str, Enum):
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class Permission(str, Enum):
    # Document Operations
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    DOCUMENT_DELETE = "document:delete"
    
    # RAG Actions
    RAG_SEARCH = "rag:search"
    RAG_INDEX = "rag:index"
    
    # Administration Settings
    ROLE_MANAGE = "role:manage"
    USER_MANAGE = "user:manage"
