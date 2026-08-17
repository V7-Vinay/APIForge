import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { workspacesApi } from "../../api/workspaces";
import { ApiError } from "../../api/client";
import { useToast } from "../../contexts/ToastContext";
import { Button } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { EmptyState, Panel, Spinner } from "../../components/ui/Tabs";
import { formatDateTime, slugify } from "../../utils/format";
import type { Workspace } from "../../types/api";

export function WorkspaceListPage() {
  const navigate = useNavigate();
  const toast = useToast();

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const list = await workspacesApi.list();
      setWorkspaces(list);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "Could not load workspaces.";
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // Initial load only
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openCreate() {
    setName("");
    setSlug("");
    setSlugTouched(false);
    setFormError(null);
    setModalOpen(true);
  }

  function handleNameChange(value: string) {
    setName(value);
    if (!slugTouched) setSlug(slugify(value));
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    const trimmedName = name.trim();
    const trimmedSlug = slugify(slug || trimmedName);
    if (trimmedName.length < 2) {
      setFormError("Name must be at least 2 characters.");
      return;
    }
    if (trimmedSlug.length < 2) {
      setFormError("Slug must be at least 2 characters.");
      return;
    }
    setSaving(true);
    try {
      const workspace = await workspacesApi.create(trimmedName, trimmedSlug);
      toast.success("Workspace created.");
      setModalOpen(false);
      navigate(`/workspaces/${workspace.id}/overview`);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : "Could not create workspace.";
      setFormError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page workspace-list-page">
      <header className="page-header">
        <div>
          <h1>Workspaces</h1>
          <p>Choose a workspace or create a new one.</p>
        </div>
        <Button variant="primary" onClick={openCreate}>
          New workspace
        </Button>
      </header>

      {loading ? (
        <div className="page-loading">
          <Spinner label="Loading workspaces" />
        </div>
      ) : workspaces.length === 0 ? (
        <EmptyState
          title="No workspaces yet"
          description="Create your first workspace to organize collections and collaborate."
          action={
            <Button variant="primary" onClick={openCreate}>
              Create workspace
            </Button>
          }
        />
      ) : (
        <div className="workspace-cards">
          {workspaces.map((ws) => (
            <Panel key={ws.id} className="workspace-card">
              <button
                type="button"
                className="workspace-card-button"
                onClick={() => navigate(`/workspaces/${ws.id}/overview`)}
              >
                <strong>{ws.name}</strong>
                <span className="muted">{ws.slug}</span>
                <span className="muted">
                  Updated {formatDateTime(ws.updated_at)}
                </span>
              </button>
            </Panel>
          ))}
        </div>
      )}

      <Modal
        open={modalOpen}
        title="Create workspace"
        onClose={() => !saving && setModalOpen(false)}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setModalOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form="create-workspace-form"
              variant="primary"
              loading={saving}
            >
              Create
            </Button>
          </>
        }
      >
        <form
          id="create-workspace-form"
          className="stack-form"
          onSubmit={handleCreate}
        >
          <Field label="Name" htmlFor="ws-name">
            <Input
              id="ws-name"
              required
              minLength={2}
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              disabled={saving}
              autoFocus
            />
          </Field>
          <Field
            label="Slug"
            htmlFor="ws-slug"
            hint="Used in URLs. Lowercase letters, numbers, and hyphens."
          >
            <Input
              id="ws-slug"
              required
              minLength={2}
              pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
              value={slug}
              onChange={(e) => {
                setSlugTouched(true);
                setSlug(slugify(e.target.value));
              }}
              disabled={saving}
            />
          </Field>
          {formError ? (
            <p className="form-error" role="alert">
              {formError}
            </p>
          ) : null}
        </form>
      </Modal>
    </div>
  );
}
