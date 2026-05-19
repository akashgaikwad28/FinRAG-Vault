from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repository import UserRepository
from app.repositories.role_repository import RoleRepository
from app.models.user import User
from app.schemas.user import UserUpdate
from app.core.security import get_password_hash
from app.core.exceptions import EntityNotFound, FinRAGException
from typing import List, Optional, Tuple
import uuid
import logging

logger = logging.getLogger("finragvault.services.user")


class UserService:
    """Business service orchestrator managing user accounts, updates, and soft deletes."""

    @staticmethod
    async def create_user(
        session: AsyncSession,
        username: str,
        email: str,
        password: str,
        company_name: Optional[str] = None,
        role_names: Optional[List[str]] = None
    ) -> User:
        """Validates credentials and provisions a new user with designated roles."""
        # Validate unique username
        existing_username = await UserRepository.get_by_username(session, username)
        if existing_username:
            raise FinRAGException(f"Username '{username}' is already registered", status_code=400)
            
        # Validate unique email
        existing_email = await UserRepository.get_by_email(session, email)
        if existing_email:
            raise FinRAGException(f"Email '{email}' is already registered", status_code=400)
            
        # Fetch matching Role entities
        roles_to_attach = []
        if role_names:
            roles_to_attach = await RoleRepository.get_by_names(session, role_names)
            if len(roles_to_attach) != len(role_names):
                raise EntityNotFound("One or more assigned roles could not be found")
        else:
            # Assign a default "Client" role if not specified
            client_role = await RoleRepository.get_by_name(session, "Client")
            if client_role:
                roles_to_attach.append(client_role)
                
        # Hash password and save user
        hashed = get_password_hash(password)
        user = await UserRepository.create(
            session=session,
            username=username,
            email=email,
            hashed_password=hashed,
            company_name=company_name,
            roles=roles_to_attach
        )
        return user

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User:
        """Fetches a user by UUID, raising EntityNotFound if missing."""
        user = await UserRepository.get_by_id(session, user_id)
        if not user:
            raise EntityNotFound(f"User with ID '{user_id}' not found")
        return user

    @staticmethod
    async def get_user_by_username(session: AsyncSession, username: str) -> User:
        """Fetches an active user by username, raising EntityNotFound if missing."""
        user = await UserRepository.get_by_username(session, username)
        if not user:
            raise EntityNotFound(f"User '{username}' not found")
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
        """Provides a paginated and sorted list of users, returns (items, total_count)."""
        # Restrict sortable attributes
        valid_sort_fields = ["username", "email", "company_name", "created_at"]
        if sort_by not in valid_sort_fields:
            sort_by = "username"
            
        return await UserRepository.list_users(
            session=session,
            page=page,
            page_size=page_size,
            role_name=role_name,
            company_name=company_name,
            sort_by=sort_by,
            sort_order=sort_order
        )

    @staticmethod
    async def update_user(session: AsyncSession, user_id: uuid.UUID, updates: UserUpdate) -> User:
        """Applies dynamic properties and role sets to an active user record."""
        user = await UserService.get_user_by_id(session, user_id)
        
        # Apply standard field properties
        if updates.username is not None:
            if updates.username != user.username:
                existing = await UserRepository.get_by_username(session, updates.username)
                if existing:
                    raise FinRAGException(f"Username '{updates.username}' already in use", status_code=400)
            user.username = updates.username
            
        if updates.email is not None:
            if updates.email != user.email:
                existing = await UserRepository.get_by_email(session, updates.email)
                if existing:
                    raise FinRAGException(f"Email '{updates.email}' already in use", status_code=400)
            user.email = updates.email
            
        if updates.company_name is not None:
            user.company_name = updates.company_name
            
        if updates.is_active is not None:
            user.is_active = updates.is_active
            
        # Re-attach roles if provided
        if updates.roles is not None:
            roles_to_attach = await RoleRepository.get_by_names(session, updates.roles)
            if len(roles_to_attach) != len(updates.roles):
                raise EntityNotFound("One or more assigned roles not found")
            # Clear old and map new
            user.roles.clear()
            user.roles.extend(roles_to_attach)
            
        session.add(user)
        await session.flush()
        logger.info(f"Updated User record: {user.username} (ID: {user.id})")
        return user

    @staticmethod
    async def soft_delete_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Performs an audit-safe soft-delete on a user record by UUID."""
        user = await UserService.get_user_by_id(session, user_id)
        await UserRepository.soft_delete(session, user)
