from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.role import Role
from typing import List, Optional
import logging

logger = logging.getLogger("finragvault.repositories.role")


class RoleRepository:
    """Asynchronous Repository handling relational DB operations for the Role entity."""

    @staticmethod
    async def get_by_name(session: AsyncSession, name: str) -> Optional[Role]:
        """Fetches a single Role configuration by its unique name string.
        
        Args:
            session (AsyncSession): Active database session.
            name (str): The case-sensitive name of the role.
            
        Returns:
            Optional[Role]: The fetched Role model, or None if not found.
        """
        query = select(Role).where(Role.name == name)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_names(session: AsyncSession, names: List[str]) -> List[Role]:
        """Fetches multiple Role configurations matching a list of name strings.
        
        Args:
            session (AsyncSession): Active database session.
            names (List[str]): List of target role names.
            
        Returns:
            List[Role]: List of matching Role models.
        """
        if not names:
            return []
        query = select(Role).where(Role.name.in_(names))
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_all(session: AsyncSession) -> List[Role]:
        """Retrieves all defined Roles from the database.
        
        Args:
            session (AsyncSession): Active database session.
            
        Returns:
            List[Role]: List of all Role models in the system.
        """
        query = select(Role).order_by(Role.name)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def create(session: AsyncSession, name: str, description: Optional[str] = None) -> Role:
        """Constructs and persists a new Role entity in the database.
        
        Args:
            session (AsyncSession): Active database session.
            name (str): Unique identifier name of the role.
            description (Optional[str]): Informative explanation of permissions.
            
        Returns:
            Role: The newly created and persisted Role.
        """
        role = Role(name=name, description=description)
        session.add(role)
        await session.flush()  # Extract primary UUID keys without committing transaction
        logger.info(f"Created role record: {name} (ID: {role.id})")
        return role
