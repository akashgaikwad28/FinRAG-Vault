from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
import uuid
from typing import List

from app.core.config import settings
from app.core.database import get_async_session
from app.core.exceptions import AuthenticationError, PermissionDenied
from app.repositories.user_repository import UserRepository
from app.models.user import User
from app.utils.constants import Permission, SystemRole
from app.utils.permissions import verify_role_permissions

# OAuth2 scheme point targeting our JWT authentication endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    description="JWT Bearer token verification"
)

# Re-export database dependency for route handlers compatibility
get_db = get_async_session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db)
) -> User:
    """Decodes the JWT bearer token, checks database records, and returns the authenticated User.
    
    Raises:
        AuthenticationError: If token decode fails or if the user is soft-deleted/deactivated.
    """
    try:
        # Decode claims
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise AuthenticationError("Session token missing subject claim")
            
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise AuthenticationError("Invalid session signature or expired token")
        
    # Query matching User, eager loading roles
    user = await UserRepository.get_by_id(session, user_id)
    if not user:
        raise AuthenticationError("User session context not found")
        
    if not user.is_active:
        raise AuthenticationError("Account has been deactivated")
        
    return user


def require_permissions(permissions: List[Permission]):
    """Dynamic RBAC endpoint guard checking for necessary permissions across a user's roles.
    
    Args:
        permissions (List[Permission]): Clearance parameters.
        
    Returns:
        Dependency: Injectable FastAPI dependency.
    """
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_roles = [role.name for role in current_user.roles]
        
        # Verify permissions matching user roles
        if not verify_role_permissions(user_roles, permissions):
            raise PermissionDenied("Forbidden: You do not possess the required clearances")
            
        return current_user
        
    return dependency
