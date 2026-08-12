from app.core.permissions import Permission, role_has_permission
from app.models.workspace import WorkspaceRole


def test_owner_has_every_permission():
    for permission in Permission:
        assert role_has_permission(WorkspaceRole.OWNER, permission)


def test_viewer_is_read_only():
    assert role_has_permission(WorkspaceRole.VIEWER, Permission.VIEW_WORKSPACE)
    assert role_has_permission(WorkspaceRole.VIEWER, Permission.VIEW_HISTORY)
    assert not role_has_permission(WorkspaceRole.VIEWER, Permission.EDIT_REQUESTS)
    assert not role_has_permission(WorkspaceRole.VIEWER, Permission.MANAGE_MEMBERS)


def test_editor_can_execute_but_cannot_manage_members():
    assert role_has_permission(WorkspaceRole.EDITOR, Permission.EXECUTE_REQUESTS)
    assert role_has_permission(WorkspaceRole.EDITOR, Permission.EDIT_REQUESTS)
    assert not role_has_permission(WorkspaceRole.EDITOR, Permission.MANAGE_MEMBERS)
