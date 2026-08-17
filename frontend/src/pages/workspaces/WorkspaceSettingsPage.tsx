import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { workspacesApi } from "../../api/workspaces";
import { ApiError } from "../../api/client";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { Button } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Input";
import { ConfirmDialog } from "../../components/ui/Modal";
import { Panel, Spinner } from "../../components/ui/Tabs";
import { formatDateTime } from "../../utils/format";
import {
  canDeleteWorkspace,
  canManageWorkspace,
} from "../../utils/permissions";

export function WorkspaceSettingsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const {
    workspace,
    members,
    role,
    loading,
    refreshWorkspace,
    refreshWorkspaces,
  } = useWorkspace();

  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (workspace) setName(workspace.name);
  }, [workspace]);

  const canRename = canManageWorkspace(role);
  const canDelete = canDeleteWorkspace(role);
  const creator = members.find((m) => m.user_id === workspace?.created_by);

  async function handleRename(event: FormEvent) {
    event.preventDefault();
    if (!workspaceId || !canRename) return;
    const trimmed = name.trim();
    if (trimmed.length < 2) {
      toast.error("Name must be at least 2 characters.");
      return;
    }
    if (trimmed === workspace?.name) return;
    setSaving(true);
    try {
      await workspacesApi.update(workspaceId, trimmed);
      await refreshWorkspace();
      await refreshWorkspaces();
      toast.success("Workspace renamed.");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Could not rename workspace.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!workspaceId || !canDelete) return;
    setDeleting(true);
    try {
      await workspacesApi.remove(workspaceId);
      toast.success("Workspace deleted.");
      await refreshWorkspaces();
      navigate("/workspaces", { replace: true });
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Could not delete workspace.",
      );
      setDeleting(false);
      setDeleteOpen(false);
    }
  }

  if (loading && !workspace) {
    return (
      <div className="page-loading">
        <Spinner label="Loading settings" />
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="page">
        <h1>Workspace not found</h1>
      </div>
    );
  }

  return (
    <div className="page workspace-settings-page">
      <header className="page-header">
        <div>
          <h1>Workspace settings</h1>
          <p>Manage identity and ownership for this workspace.</p>
        </div>
      </header>

      <Panel title="Identity">
        <dl className="detail-list">
          <div>
            <dt>Slug</dt>
            <dd>
              <code>{workspace.slug}</code>
            </dd>
          </div>
          <div>
            <dt>Creator</dt>
            <dd>
              {creator
                ? `${creator.name} · ${creator.email}`
                : workspace.created_by}
            </dd>
          </div>
          <div>
            <dt>Created</dt>
            <dd>{formatDateTime(workspace.created_at)}</dd>
          </div>
          <div>
            <dt>Updated</dt>
            <dd>{formatDateTime(workspace.updated_at)}</dd>
          </div>
        </dl>
      </Panel>

      <Panel title="Rename">
        {canRename ? (
          <form className="stack-form" onSubmit={handleRename}>
            <Field label="Name" htmlFor="settings-ws-name">
              <Input
                id="settings-ws-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                minLength={2}
                required
                disabled={saving}
              />
            </Field>
            <Button type="submit" variant="primary" loading={saving}>
              Save name
            </Button>
          </form>
        ) : (
          <p className="muted">
            You need Admin or Owner permissions to rename this workspace.
          </p>
        )}
      </Panel>

      {canDelete ? (
        <Panel title="Danger zone" className="danger-panel">
          <p>
            Deleting <strong>{workspace.name}</strong> permanently removes
            collections, environments, and membership. This cannot be undone.
          </p>
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>
            Delete workspace
          </Button>
        </Panel>
      ) : null}

      <ConfirmDialog
        open={deleteOpen}
        title="Delete workspace?"
        message={`Delete “${workspace.name}”? All workspace data will be removed permanently.`}
        confirmLabel="Delete workspace"
        danger
        loading={deleting}
        onConfirm={() => void handleDelete()}
        onClose={() => !deleting && setDeleteOpen(false)}
      />
    </div>
  );
}
