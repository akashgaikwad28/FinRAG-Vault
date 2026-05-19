from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, SoftDeleteMixin
from app.models.role import user_roles, Role
import uuid
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.audit_log import AuditLog


class User(Base, TimestampMixin, SoftDeleteMixin):
    """Database model representing application Users in FinRAG Vault."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(),
        default=True,
        nullable=False
    )
    
    # Critical field for Client isolation: represents the company name they represent
    company_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True
    )

    # Relationships
    roles: Mapped[List[Role]] = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin"  # Eager load roles
    )
    
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="uploader",
        cascade="all, delete-orphan"
    )
    
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
