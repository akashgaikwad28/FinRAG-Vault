from app.utils.constants import SystemRole, Permission
from typing import List, Dict, Set


# In-memory singleton caching role-to-permissions mapping matrix
ROLE_PERMISSIONS: Dict[SystemRole, Set[Permission]] = {
    SystemRole.ADMIN: {p for p in Permission},
    SystemRole.ANALYST: {
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.RAG_SEARCH,
        Permission.RAG_INDEX
    },
    SystemRole.AUDITOR: {
        Permission.DOCUMENT_READ,
        Permission.RAG_SEARCH
    },
    SystemRole.CLIENT: {
        Permission.DOCUMENT_READ,
        Permission.RAG_SEARCH
    }
}


def verify_role_permissions(user_roles: List[str], required_permissions: List[Permission]) -> bool:
    """Validates if the user's role set carries the required permission clearances.
    
    Args:
        user_roles (List[str]): List of role names assigned to the user.
        required_permissions (List[Permission]): List of mandatory permissions for the endpoint.
        
    Returns:
        bool: True if authorized, False otherwise.
    """
    # Administrators bypass all checks
    if SystemRole.ADMIN.value in user_roles:
        return True
        
    # Gather union of all permissions granted across assigned roles
    granted_permissions: Set[Permission] = set()
    for role_name in user_roles:
        try:
            role_enum = SystemRole(role_name)
            if role_enum in ROLE_PERMISSIONS:
                granted_permissions.update(ROLE_PERMISSIONS[role_enum])
        except ValueError:
            # Custom roles not explicitly in SystemRole are ignored or default to empty
            pass
            
    # Verify all required clearances are satisfied
    return all(req in granted_permissions for req in required_permissions)
