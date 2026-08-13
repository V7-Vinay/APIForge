from enum import Enum

from app.models.workspace import WorkspaceRole


class Permission(str, Enum):
    VIEW_WORKSPACE = "workspace:view"
    MANAGE_WORKSPACE = "workspace:manage"
    MANAGE_MEMBERS = "workspace:members:manage"
    MANAGE_COLLECTIONS = "collections:manage"
    EDIT_REQUESTS = "requests:edit"
    EXECUTE_REQUESTS = "requests:execute"
    VIEW_HISTORY = "history:view"
    EDIT_DOCUMENTATION = "documentation:edit"
    MANAGE_ENVIRONMENTS = "environments:manage"


ROLE_PERMISSIONS: dict[WorkspaceRole, frozenset[Permission]] = {
    WorkspaceRole.OWNER: frozenset(Permission),
    WorkspaceRole.ADMIN: frozenset(
        {
            Permission.VIEW_WORKSPACE,
            Permission.MANAGE_WORKSPACE,
            Permission.MANAGE_MEMBERS,
            Permission.MANAGE_COLLECTIONS,
            Permission.EDIT_REQUESTS,
            Permission.EXECUTE_REQUESTS,
            Permission.VIEW_HISTORY,
            Permission.EDIT_DOCUMENTATION,
            Permission.MANAGE_ENVIRONMENTS,
        }
    ),
    WorkspaceRole.EDITOR: frozenset(
        {
            Permission.VIEW_WORKSPACE,
            Permission.MANAGE_COLLECTIONS,
            Permission.EDIT_REQUESTS,
            Permission.EXECUTE_REQUESTS,
            Permission.VIEW_HISTORY,
            Permission.EDIT_DOCUMENTATION,
        }
    ),
    WorkspaceRole.VIEWER: frozenset(
        {
            Permission.VIEW_WORKSPACE,
            Permission.VIEW_HISTORY,
        }
    ),
}


def role_has_permission(role: WorkspaceRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
