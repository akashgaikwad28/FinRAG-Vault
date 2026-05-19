from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.core.exceptions import AuthenticationError
from app.schemas.auth import Token
from typing import Optional
import logging

logger = logging.getLogger("finragvault.services.auth")


class AuthService:
    """Business service orchestrator managing user authentication, login verifications, and registration."""

    @staticmethod
    async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
        """Verifies email credentials and password validation, returning the User model.
        
        Raises:
            AuthenticationError: Upon user mismatch, incorrect password, or inactive status.
        """
        # Fetch active user by email
        user = await UserRepository.get_by_email(session, email)
        if not user:
            logger.warning(f"Authentication attempt failed: email '{email}' not found.")
            raise AuthenticationError("Invalid email or password")
            
        # Verify passwords
        if not verify_password(password, user.hashed_password):
            logger.warning(f"Authentication attempt failed: incorrect password for email '{email}'.")
            raise AuthenticationError("Invalid email or password")
            
        # Verify active status
        if not user.is_active:
            logger.warning(f"Authentication attempt failed: account is inactive for email '{email}'.")
            raise AuthenticationError("Account has been deactivated. Please contact support.")
            
        return user

    @staticmethod
    async def login_user(session: AsyncSession, email: str, password: str) -> Token:
        """Logs in a user, returning a signed JWT access token envelope."""
        user = await AuthService.authenticate_user(session, email, password)
        
        # Issue JWT Access Token
        access_token = create_access_token(subject=str(user.id))
        
        logger.info(f"Successful user login: '{user.username}' (ID: {user.id})")
        return Token(access_token=access_token, token_type="bearer")

    @staticmethod
    async def register_user(
        session: AsyncSession,
        username: str,
        email: str,
        password: str,
        company_name: Optional[str] = None
    ) -> User:
        """Registers a new user account, defaulting role permissions to 'Client'."""
        # Registers via UserService, which assigns the default "Client" role
        user = await UserService.create_user(
            session=session,
            username=username,
            email=email,
            password=password,
            company_name=company_name,
            role_names=["Client"]
        )
        logger.info(f"Registered new client user: '{username}' (ID: {user.id}, Company: '{company_name}')")
        return user
