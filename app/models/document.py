from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, SoftDeleteMixin
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User


class Document(Base, TimestampMixin, SoftDeleteMixin):
    """Database model representing uploaded Financial Documents in FinRAG Vault."""
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    
    # Target company represented by the financial asset
    company_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    
    # Category of document: e.g. "invoice", "report", "contract"
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    
    # Link to user who uploaded this document
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    storage_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False
    )
    
    # Ingestion status lifecycle: "processing", "indexed", "failed"
    status: Mapped[str] = mapped_column(
        String(20),
        default="processing",
        nullable=False,
        index=True
    )
    
    # Description of ingestion failure if status resolves to "failed"
    error_message: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True
    )

    # Relationships
    uploader: Mapped["User"] = relationship(
        "User",
        back_populates="documents",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title='{self.title}', status='{self.status}')>"
