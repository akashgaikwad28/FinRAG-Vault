from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.role_repository import RoleRepository
from app.models.role import Role
from app.core.exceptions import EntityNotFound, FinRAGException
from typing import List, Optional
import logging

logger = logging.getLogger("finragvault.services.role")


class RoleService:
    """Business service orchestrator managing roles and RBAC settings."""

    @staticmethod
    async def create_role(session: AsyncSession, name: str, description: Optional[str] = None) -> Role:
        """Validates and provisions a new system-wide role.
        
        Raises:
            FinRAGException: If a role with the same name already exists.
        """
        existing = await RoleRepository.get_by_name(session, name)
        if existing:
            raise FinRAGException(f"Role with name '{name}' already exists", status_code=400)
            
        role = await RoleRepository.create(session, name=name, description=description)
        return role

    @staticmethod
    async def get_role_by_name(session: AsyncSession, name: str) -> Role:
        """Retrieves a single role, raising a structured exception if missing."""
        role = await RoleRepository.get_by_name(session, name)
        if not role:
            raise EntityNotFound(f"Role '{name}' not found")
        return role

    @staticmethod
    async def list_all_roles(session: AsyncSession) -> List[Role]:
        """Lists all roles recorded in the database."""
        return await RoleRepository.get_all(session)
