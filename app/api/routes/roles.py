from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.deps.deps import get_db, require_permissions
from app.schemas.auth import StandardResponse
from app.schemas.role import RoleResponse, RoleCreate
from app.services.role_service import RoleService
from app.models.user import User
from app.utils.constants import Permission
from app.api.routes.auth import record_audit_log

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get(
    "",
    response_model=StandardResponse,
    summary="List all role configurations",
    description="Returns all defined security role schemas in the system. Guarded by ROLE_MANAGE clearance."
)
async def list_roles(
    session: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_permissions([Permission.ROLE_MANAGE]))
) -> StandardResponse:
    roles = await RoleService.list_all_roles(session)
    role_schemas = [RoleResponse.model_validate(r) for r in roles]
    return StandardResponse(
        success=True,
        message="Roles retrieved successfully",
        data=role_schemas
    )


@router.post(
    "",
    response_model=StandardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Role schema",
    description="Provisions a new granular security group name. Guarded by ROLE_MANAGE clearance."
)
async def create_role(
    payload: RoleCreate,
    session: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_permissions([Permission.ROLE_MANAGE]))
) -> StandardResponse:
    async with session.begin():
        role = await RoleService.create_role(session, name=payload.name, description=payload.description)
        await record_audit_log(session, f"created_role_schema: {role.name}", admin_user.id)
        
    role_data = RoleResponse.model_validate(role)
    return StandardResponse(
        success=True,
        message="Role schema created successfully",
        data=role_data
    )


@router.get(
    "/{name}",
    response_model=StandardResponse,
    summary="Get role schema by name",
    description="Returns details for a target Role schema name. Guarded by ROLE_MANAGE clearance."
)
async def get_role_by_name(
    name: str,
    session: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_permissions([Permission.ROLE_MANAGE]))
) -> StandardResponse:
    role = await RoleService.get_role_by_name(session, name)
    role_data = RoleResponse.model_validate(role)
    return StandardResponse(
        success=True,
        message="Role schema retrieved",
        data=role_data
    )
