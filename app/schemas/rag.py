from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from typing import List, Optional


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Semantic text query to search the FinRAG Vault", examples=["What is the company's financial risk related to debt?"])
    
    # Metadata filters
    company_name: Optional[str] = Field(None, description="Filter search boundary by company name (Client role enforces this matching their company)", examples=["Acme Corp"])
    document_type: Optional[str] = Field(None, description="Filter search by document type: 'invoice', 'report', 'contract'", examples=["report"])
    uploaded_by: Optional[uuid.UUID] = Field(None, description="Filter search by user who uploaded the document")
    start_date: Optional[datetime] = Field(None, description="Filter results uploaded after this date")
    end_date: Optional[datetime] = Field(None, description="Filter results uploaded before this date")


class RAGSearchResultItem(BaseModel):
    chunk_id: str = Field(..., description="Unique chunk UUID tracker string")
    chunk_text: str = Field(..., description="Extract segment text block")
    score: float = Field(..., description="Cross-encoder relevance score (range -10 to +10, or normalized)", examples=[0.895])
    document_id: uuid.UUID = Field(..., description="Parent document UUID")
    title: str = Field(..., description="Document title descriptor")
    company_name: str = Field(..., description="Company name")
    document_type: str = Field(..., description="Document category ('invoice', 'report', 'contract')")
    chunk_index: int = Field(..., description="Index order of chunk within parent document")


class RAGContextItem(BaseModel):
    chunk_id: str
    chunk_text: str
    chunk_index: int
    created_at: str


class RAGContextResponse(BaseModel):
    document_id: uuid.UUID
    title: str
    chunks: List[RAGContextItem]
