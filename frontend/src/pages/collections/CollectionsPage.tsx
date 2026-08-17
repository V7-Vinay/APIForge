import CollectionExplorer from "../../features/collections/CollectionExplorer";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { EmptyState, Spinner } from "../../components/ui/Tabs";
import { Button } from "../../components/ui/Button";
import { canManageCollections } from "../../utils/permissions";
import { useState } from "react";
import { collectionsApi } from "../../api/resources";
import { ApiError } from "../../api/client";
import { useToast } from "../../contexts/ToastContext";
import { useParams } from "react-router-dom";
import { Field, Input, Textarea } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";

export default function CollectionsPage() {
  const { workspaceId = "" } = useParams();
  const { collections, loading, treeLoading, role, refreshTree } = useWorkspace();
  const toast = useToast();
  const manage = canManageCollections(role);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) {
    return <Spinner label="Loading workspace" />;
  }

  async function createFirst() {
    if (!name.trim()) {
      toast.warning("Name is required.");
      return;
    }
    setBusy(true);
    try {
      await collectionsApi.create(workspaceId, name.trim(), description.trim() || undefined);
      toast.success("Collection created");
      setWelcomeOpen(false);
      setName("");
      setDescription("");
      await refreshTree();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create collection.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page collections-page">
      {!treeLoading && collections.length === 0 ? (
        <EmptyState
          title="Welcome to your API workspace"
          description="Create a collection to group folders and requests. You can import an OpenAPI spec from Documentation anytime."
          action={
            manage ? (
              <Button variant="primary" onClick={() => setWelcomeOpen(true)}>
                Create your first collection
              </Button>
            ) : (
              <p className="muted">Ask a workspace admin to create a collection.</p>
            )
          }
        />
      ) : (
        <CollectionExplorer />
      )}

      <Modal
        open={welcomeOpen}
        title="Create collection"
        onClose={() => !busy && setWelcomeOpen(false)}
        footer={
          <>
            <Button variant="ghost" disabled={busy} onClick={() => setWelcomeOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={busy} onClick={() => void createFirst()}>
              Create
            </Button>
          </>
        }
      >
        <Field label="Name">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My APIs"
            autoFocus
          />
        </Field>
        <Field label="Description" hint="Optional">
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
        </Field>
      </Modal>
    </div>
  );
}
