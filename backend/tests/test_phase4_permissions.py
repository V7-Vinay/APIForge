from app.core.permissions import Permission, role_has_permission
from app.models.workspace import WorkspaceRole


def test_viewer_cannot_manage_collections_or_requests():
    assert not role_has_permission(WorkspaceRole.VIEWER, Permission.MANAGE_COLLECTIONS)
    assert not role_has_permission(WorkspaceRole.VIEWER, Permission.EDIT_REQUESTS)


def test_editor_can_manage_collections_and_requests():
    assert role_has_permission(WorkspaceRole.EDITOR, Permission.MANAGE_COLLECTIONS)
    assert role_has_permission(WorkspaceRole.EDITOR, Permission.EDIT_REQUESTS)
