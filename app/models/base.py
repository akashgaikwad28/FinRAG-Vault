from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy import MetaData
import uuid
from datetime import datetime

# Standard naming conventions for constraints in Alembic migrations
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}


class Base(DeclarativeBase):
    """Unified SQLAlchemy Declarative Base containing constraints metadata mappings."""
    metadata = MetaData(naming_convention=naming_convention)


class TimestampMixin:
    """SQLAlchemy mixin injecting auto-managed timezone aware timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        index=True,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class SoftDeleteMixin:
    """SQLAlchemy mixin enabling soft-delete workflows across database tables."""
    deleted_at: Mapped[datetime | None] = mapped_column(
        default=None,
        nullable=True
    )
    
    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
