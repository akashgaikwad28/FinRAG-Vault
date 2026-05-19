from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from typing import Optional


class DocumentBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255, description="Informative title of the financial document", examples=["Q1 2026 Balance Sheet"])
    company_name: str = Field(..., min_length=1, max_length=100, description="The targeted corporate entity name", examples=["Acme Corp"])
    document_type: str = Field(..., description="Document classification ('invoice', 'report', 'contract')", examples=["report"])


class DocumentCreate(DocumentBase):
    filename: str = Field(..., max_length=255)
    storage_path: str = Field(..., max_length=512)
    uploaded_by: uuid.UUID
    status: str = Field("processing", max_length=20)


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    status: Optional[str] = Field(None, max_length=20)
    error_message: Optional[str] = Field(None, max_length=1000)


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    filename: str
    uploaded_by: uuid.UUID
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
