from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.user import User
from app.models.role import Role
from typing import List, Optional, Tuple
import uuid
from datetime import datetime, timezone
import logging

logger = logging.getLogger("finragvault.repositories.user")


class UserRepository:
    """Asynchronous Repository handling relational DB operations for the User entity."""

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
        """Fetches a single active User record by UUID.
        
        Filters out soft-deleted records.
        """
        query = select(User).where(and_(User.id == user_id, User.deleted_at.is_(None)))
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(session: AsyncSession, username: str) -> Optional[User]:
        """Fetches an active User by their unique username string."""
        query = select(User).where(and_(User.username == username, User.deleted_at.is_(None)))
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> Optional[User]:
        """Fetches an active User by their unique email."""
        query = select(User).where(and_(User.email == email, User.deleted_at.is_(None)))
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        username: str,
        email: str,
        hashed_password: str,
        company_name: Optional[str] = None,
        roles: Optional[List[Role]] = None
    ) -> User:
        """Constructs and persists a new User entity, attaching pre-loaded Role models."""
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            company_name=company_name,
            is_active=True
        )
        if roles:
            user.roles.extend(roles)
            
        session.add(user)
        await session.flush()
        logger.info(f"Created User record: {username} (ID: {user.id})")
        return user

    @staticmethod
    async def list_users(
        session: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        role_name: Optional[str] = None,
        company_name: Optional[str] = None,
        sort_by: str = "username",
        sort_order: str = "asc"
    ) -> Tuple[List[User], int]:
        """Queries a paginated and filtered list of active users, returns a tuple (items, total_count)."""
        # Ensure page boundaries
        skip = (page - 1) * page_size
        
        # Build base filters
        filters = [User.deleted_at.is_(None)]
        if company_name:
            filters.append(User.company_name == company_name)
            
        # Build query
        query = select(User).where(and_(*filters))
        
        # Add role join if filter specified
        if role_name:
            query = query.join(User.roles).where(Role.name == role_name)
            
        # Add sorting
        sort_column = getattr(User, sort_by, User.username)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
            
        # Execute total count query in parallel
        count_filters = [User.deleted_at.is_(None)]
        if company_name:
            count_filters.append(User.company_name == company_name)
            
        count_query = select(func.count(User.id)).where(and_(*count_filters))
        if role_name:
            count_query = count_query.join(User.roles).where(Role.name == role_name)
            
        count_result = await session.execute(count_query)
        total = count_result.scalar_one()
        
        # Execute main list query
        query = query.offset(skip).limit(page_size)
        result = await session.execute(query)
        users = list(result.scalars().all())
        
        return users, total

    @staticmethod
    async def soft_delete(session: AsyncSession, user: User) -> None:
        """Applies a soft-delete timestamp to a User, marking them inactive."""
        user.deleted_at = datetime.now(timezone.utc)
        user.is_active = False
        session.add(user)
        await session.flush()
        logger.info(f"Soft deleted User record: {user.username} (ID: {user.id})")
