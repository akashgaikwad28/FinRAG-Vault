from fastapi import APIRouter, Depends, Form, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.api.deps.deps import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, Token, StandardResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.models.audit_log import AuditLog
from app.core.exceptions import AuthenticationError

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def record_audit_log(session: AsyncSession, action: str, user_id: Any = None) -> None:
    """Helper utility to insert an audit trail record within the current transaction context."""
    log_entry = AuditLog(user_id=user_id, action=action)
    session.add(log_entry)
    await session.flush()


@router.post(
    "/register",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Client account",
    description="Provisions a new User account, assigning a default Client role and isolating them under the provided company name."
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db)
) -> StandardResponse:
    # Open isolated write transaction
    async with session.begin():
        user = await AuthService.register_user(
            session=session,
            username=payload.username,
            email=payload.email,
            password=payload.password,
            company_name=payload.company_name
        )
        # Record registration audit
        await record_audit_log(session, "user_registered", user.id)
        
    user_data = UserResponse.model_validate(user)
    return StandardResponse(
        success=True,
        message="User registered successfully",
        data=user_data
    )


@router.post(
    "/login",
    response_model=StandardResponse,
    summary="Authenticate User and return JWT token",
    description="Verifies user credentials (email + password) and generates a JWT session token."
)
async def login_json(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db)
) -> StandardResponse:
    # Explicit login validation and token issue
    token = await AuthService.login_user(
        session=session,
        email=payload.email,
        password=payload.password
    )
    
    # Eagerly retrieve the authenticated user profile for auditable records
    from app.repositories.user_repository import UserRepository
    user = await UserRepository.get_by_email(session, payload.email)
    
    async with session.begin():
        await record_audit_log(session, "user_login", user.id if user else None)
        
    return StandardResponse(
        success=True,
        message="Login successful",
        data=token.model_dump()
    )


@router.post(
    "/token",
    response_model=Token,
    summary="OAuth2 Password Flow Token Endpoint",
    description="Fulfills the OAuth2 standard token endpoint using Form parameters (username is treated as email) for native Swagger Authorize Lock."
)
async def login_oauth2_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db)
) -> Token:
    try:
        token = await AuthService.login_user(
            session=session,
            email=form_data.username,  # OAuth2 form stores input email in the username parameter
            password=form_data.password
        )
        
        from app.repositories.user_repository import UserRepository
        user = await UserRepository.get_by_email(session, form_data.username)
        
        async with session.begin():
            await record_audit_log(session, "user_login_oauth2", user.id if user else None)
            
        return token
    except AuthenticationError as exc:
        # Failed attempts are recorded in DB
        async with session.begin():
            await record_audit_log(session, f"failed_auth_attempt: {form_data.username}")
        raise exc
