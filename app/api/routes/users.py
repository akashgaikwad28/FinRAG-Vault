from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List, Optional

from app.api.deps.deps import get_db, get_current_user, require_permissions
from app.schemas.auth import StandardResponse, ValidationErrorDetail
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService
from app.models.user import User
from app.utils.constants import Permission
from app.api.routes.auth import record_audit_log

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=StandardResponse,
    summary="Get current user profile",
    description="Returns the active User session details including assigned roles and company association."
)
async def get_me(current_user: User = Depends(get_current_user)) -> StandardResponse:
    user_data = UserResponse.model_validate(current_user)
    return StandardResponse(
        success=True,
        message="Profile retrieved successfully",
        data=user_data
    )


@router.get(
    "",
    response_model=StandardResponse,
    summary="List all users",
    description="Administrative endpoint returning a paginated, sorted, and filtered list of active users. Guarded by USER_MANAGE clearance."
)
async def list_users(
    page: int = Query(1, ge=1, description="Target page number"),
    page_size: int = Query(10, ge=1, le=100, description="Records per page"),
    role: Optional[str] = Query(None, description="Filter by role name"),
    company: Optional[str] = Query(None, description="Filter by company name"),
    sort_by: str = Query("username", description="Field to sort by"),
    sort_order: str = Query("asc", description="Sort direction ('asc' or 'desc')"),
    session: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_permissions([Permission.USER_MANAGE]))
) -> StandardResponse:
    users, total = await UserService.list_users(
        session=session,
        page=page,
        page_size=page_size,
        role_name=role,
        company_name=company,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size
    
    user_schemas = [UserResponse.model_validate(u) for u in users]
    
    return StandardResponse(
        success=True,
        message="Users listed successfully",
        data={
            "items": user_schemas,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    )


@router.get(
    "/{user_id}",
    response_model=StandardResponse,
    summary="Get user details by ID",
    description="Returns full profile of any active user by their UUID. Guarded by USER_MANAGE clearance."
)
async def get_user_by_id(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_permissions([Permission.USER_MANAGE]))
) -> StandardResponse:
    user = await UserService.get_user_by_id(session, user_id)
    user_data = UserResponse.model_validate(user)
    return StandardResponse(
        success=True,
        message="User details retrieved",
        data=user_data
    )


@router.put(
    "/{user_id}",
    response_model=StandardResponse,
    summary="Update user details",
    description="Allows modification of standard user attributes and roles. Guarded by USER_MANAGE clearance."
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_permissions([Permission.USER_MANAGE]))
) -> StandardResponse:
    async with session.begin():
        user = await UserService.update_user(session, user_id, payload)
        await record_audit_log(session, f"updated_user_profile: {user.username}", admin_user.id)
        
    user_data = UserResponse.model_validate(user)
    return StandardResponse(
        success=True,
        message="User profile updated successfully",
        data=user_data
    )


@router.delete(
    "/{user_id}",
    response_model=StandardResponse,
    summary="Soft delete a user account",
    description="Marks the target user account as deactivated and soft deleted. Guarded by USER_MANAGE clearance."
)
async def delete_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_permissions([Permission.USER_MANAGE]))
) -> StandardResponse:
    # Fetch target user first to write log details
    user = await UserService.get_user_by_id(session, user_id)
    
    async with session.begin():
        await UserService.soft_delete_user(session, user_id)
        await record_audit_log(session, f"soft_deleted_user: {user.username}", admin_user.id)
        
    return StandardResponse(
        success=True,
        message=f"User '{user.username}' soft-deleted successfully",
        data=None
    )
