import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { collectionsApi, foldersApi, requestsApi } from "../../api/resources";
import { Button } from "../../components/ui/Button";
import { Field, Input, Select, Textarea } from "../../components/ui/Input";
import { ConfirmDialog, Modal } from "../../components/ui/Modal";
import { Badge, EmptyState, Spinner } from "../../components/ui/Tabs";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import type { Collection, Folder, ApiRequest } from "../../types/api";
import { methodClass } from "../../utils/format";
import { canEditRequests, canManageCollections } from "../../utils/permissions";

type DialogState =
  | { type: "create-collection" }
  | { type: "edit-collection"; collection: Collection }
  | { type: "create-folder"; collectionId: string; parentId: string | null }
  | { type: "edit-folder"; folder: Folder; folders: Folder[] }
  | { type: "create-request"; collectionId: string; folderId: string | null }
  | { type: "edit-request"; request: ApiRequest; folders: Folder[] }
  | null;

type ConfirmState =
  | { type: "collection"; id: string; name: string }
  | { type: "folder"; id: string; name: string; collectionId: string }
  | { type: "request"; id: string; name: string; collectionId: string }
  | null;

function sortByPosition<T extends { position: number; name: string }>(items: T[]): T[] {
  return [...items].sort((a, b) => a.position - b.position || a.name.localeCompare(b.name));
}

function buildFolderTree(folders: Folder[], parentId: string | null): Folder[] {
  return sortByPosition(folders.filter((f) => f.parent_id === parentId));
}

export default function CollectionExplorer() {
  const { workspaceId = "", requestId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const {
    role,
    collections,
    foldersByCollection,
    requestsByCollection,
    treeLoading,
    refreshTree,
    loadCollectionChildren,
    removeRequestLocal,
  } = useWorkspace();

  const manage = canManageCollections(role);
  const editRequests = canEditRequests(role);

  const [expandedCollections, setExpandedCollections] = useState<Record<string, boolean>>({});
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({});
  const [dialog, setDialog] = useState<DialogState>(null);
  const [confirm, setConfirm] = useState<ConfirmState>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [parentId, setParentId] = useState<string>("");

  const sortedCollections = useMemo(() => sortByPosition(collections), [collections]);

  function toggleCollection(id: string) {
    setExpandedCollections((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function toggleFolder(id: string) {
    setExpandedFolders((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function openCreateCollection() {
    setName("");
    setDescription("");
    setDialog({ type: "create-collection" });
  }

  function openEditCollection(collection: Collection) {
    setName(collection.name);
    setDescription(collection.description ?? "");
    setDialog({ type: "edit-collection", collection });
  }

  function openCreateFolder(collectionId: string, parent: string | null) {
    setName("");
    setParentId(parent ?? "");
    setDialog({ type: "create-folder", collectionId, parentId: parent });
  }

  function openEditFolder(folder: Folder) {
    const folders = foldersByCollection[folder.collection_id] ?? [];
    setName(folder.name);
    setParentId(folder.parent_id ?? "");
    setDialog({ type: "edit-folder", folder, folders });
  }

  function openCreateRequest(collectionId: string, folderId: string | null) {
    setName("New Request");
    setDialog({ type: "create-request", collectionId, folderId });
  }

  function openEditRequest(request: ApiRequest) {
    const folders = foldersByCollection[request.collection_id] ?? [];
    setName(request.name);
    setParentId(request.folder_id ?? "");
    setDialog({ type: "edit-request", request, folders });
  }

  async function submitDialog() {
    if (!dialog) return;
    setBusy(true);
    try {
      if (dialog.type === "create-collection") {
        if (!name.trim()) throw new Error("Collection name is required.");
        await collectionsApi.create(workspaceId, name.trim(), description.trim() || undefined);
        toast.success("Collection created");
        await refreshTree();
      } else if (dialog.type === "edit-collection") {
        if (!name.trim()) throw new Error("Collection name is required.");
        await collectionsApi.update(dialog.collection.id, {
          name: name.trim(),
          description: description.trim() || null,
        });
        toast.success("Collection updated");
        await refreshTree();
      } else if (dialog.type === "create-folder") {
        if (!name.trim()) throw new Error("Folder name is required.");
        await foldersApi.create(
          dialog.collectionId,
          name.trim(),
          parentId || dialog.parentId || null,
        );
        toast.success("Folder created");
        await loadCollectionChildren(dialog.collectionId);
        setExpandedCollections((prev) => ({ ...prev, [dialog.collectionId]: true }));
      } else if (dialog.type === "edit-folder") {
        if (!name.trim()) throw new Error("Folder name is required.");
        const nextParent = parentId || null;
        if (nextParent === dialog.folder.id) {
          throw new Error("A folder cannot be its own parent.");
        }
        await foldersApi.update(dialog.folder.id, {
          name: name.trim(),
          parent_id: nextParent,
        });
        toast.success("Folder updated");
        await loadCollectionChildren(dialog.folder.collection_id);
      } else if (dialog.type === "create-request") {
        if (!name.trim()) throw new Error("Request name is required.");
        const created = await requestsApi.create(dialog.collectionId, {
          name: name.trim(),
          method: "GET",
          url: "https://example.com",
          headers: [],
          query_params: [],
          body: null,
          auth_config: { type: "none" },
          folder_id: dialog.folderId,
        });
        toast.success("Request created");
        await loadCollectionChildren(dialog.collectionId);
        setExpandedCollections((prev) => ({ ...prev, [dialog.collectionId]: true }));
        if (dialog.folderId) {
          setExpandedFolders((prev) => ({ ...prev, [dialog.folderId!]: true }));
        }
        navigate(`/workspaces/${workspaceId}/requests/${created.id}`);
      } else if (dialog.type === "edit-request") {
        if (!name.trim()) throw new Error("Request name is required.");
        const nextFolder = parentId || null;
        await requestsApi.update(dialog.request.id, {
          name: name.trim(),
          folder_id: nextFolder,
        });
        toast.success("Request updated");
        await loadCollectionChildren(dialog.request.collection_id);
      }
      setDialog(null);
    } catch (err) {
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!confirm) return;
    setBusy(true);
    try {
      if (confirm.type === "collection") {
        await collectionsApi.remove(confirm.id);
        toast.success("Collection deleted");
        await refreshTree();
      } else if (confirm.type === "folder") {
        await foldersApi.remove(confirm.id);
        toast.success("Folder deleted");
        await loadCollectionChildren(confirm.collectionId);
      } else {
        await requestsApi.remove(confirm.id);
        removeRequestLocal(confirm.id, confirm.collectionId);
        toast.success("Request deleted");
        if (requestId === confirm.id) {
          navigate(`/workspaces/${workspaceId}/collections`);
        }
        await loadCollectionChildren(confirm.collectionId);
      }
      setConfirm(null);
    } catch (err) {
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setBusy(false);
    }
  }

  async function reorderCollection(collection: Collection, direction: -1 | 1) {
    const list = sortedCollections;
    const index = list.findIndex((c) => c.id === collection.id);
    const swapWith = list[index + direction];
    if (!swapWith) return;
    setBusy(true);
    try {
      await Promise.all([
        collectionsApi.reorder(collection.id, swapWith.position),
        collectionsApi.reorder(swapWith.id, collection.position),
      ]);
      await refreshTree();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not reorder.");
    } finally {
      setBusy(false);
    }
  }

  async function reorderFolder(folder: Folder, siblings: Folder[], direction: -1 | 1) {
    const list = sortByPosition(siblings);
    const index = list.findIndex((f) => f.id === folder.id);
    const swapWith = list[index + direction];
    if (!swapWith) return;
    setBusy(true);
    try {
      await Promise.all([
        foldersApi.reorder(folder.id, swapWith.position),
        foldersApi.reorder(swapWith.id, folder.position),
      ]);
      await loadCollectionChildren(folder.collection_id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not reorder.");
    } finally {
      setBusy(false);
    }
  }

  async function reorderRequest(
    request: ApiRequest,
    siblings: ApiRequest[],
    direction: -1 | 1,
  ) {
    const list = sortByPosition(siblings);
    const index = list.findIndex((r) => r.id === request.id);
    const swapWith = list[index + direction];
    if (!swapWith) return;
    setBusy(true);
    try {
      await Promise.all([
        requestsApi.reorder(request.id, swapWith.position),
        requestsApi.reorder(swapWith.id, request.position),
      ]);
      await loadCollectionChildren(request.collection_id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not reorder.");
    } finally {
      setBusy(false);
    }
  }

  function renderFolderNode(
    folder: Folder,
    allFolders: Folder[],
    allRequests: ApiRequest[],
    depth: number,
  ) {
    const children = buildFolderTree(allFolders, folder.id);
    const folderRequests = sortByPosition(
      allRequests.filter((r) => r.folder_id === folder.id),
    );
    const siblings = buildFolderTree(allFolders, folder.parent_id);
    const open = expandedFolders[folder.id] ?? false;

    return (
      <div key={folder.id} className="tree-node" style={{ marginLeft: depth * 12 }}>
        <div className="tree-row folder-row">
          <button
            type="button"
            className="tree-toggle"
            aria-expanded={open}
            onClick={() => toggleFolder(folder.id)}
          >
            {open ? "▾" : "▸"}
          </button>
          <span className="tree-name" onClick={() => toggleFolder(folder.id)}>
            📁 {folder.name}
          </span>
          <div className="tree-actions">
            {manage ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  title="New folder"
                  onClick={() => openCreateFolder(folder.collection_id, folder.id)}
                >
                  +Folder
                </Button>
                {editRequests ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    title="New request"
                    onClick={() => openCreateRequest(folder.collection_id, folder.id)}
                  >
                    +Req
                  </Button>
                ) : null}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => openEditFolder(folder)}
                >
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={siblings[0]?.id === folder.id}
                  onClick={() => reorderFolder(folder, siblings, -1)}
                >
                  ↑
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={siblings[siblings.length - 1]?.id === folder.id}
                  onClick={() => reorderFolder(folder, siblings, 1)}
                >
                  ↓
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setConfirm({
                      type: "folder",
                      id: folder.id,
                      name: folder.name,
                      collectionId: folder.collection_id,
                    })
                  }
                >
                  Del
                </Button>
              </>
            ) : editRequests ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => openCreateRequest(folder.collection_id, folder.id)}
              >
                +Req
              </Button>
            ) : null}
          </div>
        </div>
        {open ? (
          <div className="tree-children">
            {children.map((child) =>
              renderFolderNode(child, allFolders, allRequests, depth + 1),
            )}
            {folderRequests.map((req) => renderRequestRow(req, folderRequests, depth + 1))}
            {children.length === 0 && folderRequests.length === 0 ? (
              <div className="tree-item" style={{ marginLeft: (depth + 1) * 12 }}>
                Empty folder
                {editRequests ? (
                  <Button
                    variant="subtle"
                    size="sm"
                    onClick={() => openCreateRequest(folder.collection_id, folder.id)}
                  >
                    Add request
                  </Button>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  function renderRequestRow(request: ApiRequest, siblings: ApiRequest[], depth: number) {
    const selected = request.id === requestId;
    return (
      <div
        key={request.id}
        className={`tree-row request-row ${selected ? "selected" : ""}`}
        style={{ marginLeft: depth * 12 }}
      >
        <button
          type="button"
          className={`request-item ${selected ? "selected" : ""}`}
          onClick={() =>
            navigate(`/workspaces/${workspaceId}/requests/${request.id}`)
          }
        >
          <Badge tone="method">
            <span className={methodClass(request.method)}>{request.method}</span>
          </Badge>
          <span>{request.name}</span>
        </button>
        <div className="tree-actions">
          {editRequests ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => openEditRequest(request)}
              >
                Edit
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={siblings[0]?.id === request.id}
                onClick={() => reorderRequest(request, siblings, -1)}
              >
                ↑
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={siblings[siblings.length - 1]?.id === request.id}
                onClick={() => reorderRequest(request, siblings, 1)}
              >
                ↓
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setConfirm({
                    type: "request",
                    id: request.id,
                    name: request.name,
                    collectionId: request.collection_id,
                  })
                }
              >
                Del
              </Button>
            </>
          ) : null}
        </div>
      </div>
    );
  }

  if (treeLoading && collections.length === 0) {
    return <Spinner label="Loading collections" />;
  }

  if (collections.length === 0) {
    return (
      <EmptyState
        title="No collections yet"
        description="Organize requests into collections to start building your API workspace."
        action={
          manage ? (
            <Button variant="primary" onClick={openCreateCollection}>
              Create collection
            </Button>
          ) : undefined
        }
      />
    );
  }

  const dialogTitle =
    dialog?.type === "create-collection"
      ? "New collection"
      : dialog?.type === "edit-collection"
        ? "Edit collection"
        : dialog?.type === "create-folder"
          ? "New folder"
          : dialog?.type === "edit-folder"
            ? "Edit folder"
            : dialog?.type === "create-request"
              ? "New request"
              : dialog?.type === "edit-request"
                ? "Edit request"
                : "";

  return (
    <div className="collection-explorer">
      <div className="explorer-toolbar">
        <h2>Collections</h2>
        <div className="explorer-actions">
          <Button variant="ghost" size="sm" onClick={() => void refreshTree()} disabled={busy}>
            Refresh
          </Button>
          {manage ? (
            <Button variant="primary" size="sm" onClick={openCreateCollection}>
              New collection
            </Button>
          ) : null}
        </div>
      </div>

      <div className="collection-tree">
        {sortedCollections.map((collection, collectionIndex) => {
          const open = expandedCollections[collection.id] ?? true;
          const folders = foldersByCollection[collection.id] ?? [];
          const requests = requestsByCollection[collection.id] ?? [];
          const rootFolders = buildFolderTree(folders, null);
          const rootRequests = sortByPosition(
            requests.filter((r) => r.folder_id == null),
          );

          return (
            <div key={collection.id} className="collection-node">
              <div className={`collection ${open ? "active" : ""}`}>
                <div className="collection-title">
                  <button
                    type="button"
                    className="tree-toggle"
                    aria-expanded={open}
                    onClick={() => toggleCollection(collection.id)}
                  >
                    {open ? "▾" : "▸"}
                  </button>
                  <span onClick={() => toggleCollection(collection.id)}>
                    {collection.name}
                  </span>
                  <div className="tree-actions">
                    {manage ? (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openCreateFolder(collection.id, null)}
                        >
                          +Folder
                        </Button>
                        {editRequests ? (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openCreateRequest(collection.id, null)}
                          >
                            +Req
                          </Button>
                        ) : null}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditCollection(collection)}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={collectionIndex === 0}
                          onClick={() => void reorderCollection(collection, -1)}
                        >
                          ↑
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={collectionIndex === sortedCollections.length - 1}
                          onClick={() => void reorderCollection(collection, 1)}
                        >
                          ↓
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setConfirm({
                              type: "collection",
                              id: collection.id,
                              name: collection.name,
                            })
                          }
                        >
                          Del
                        </Button>
                      </>
                    ) : editRequests ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openCreateRequest(collection.id, null)}
                      >
                        +Req
                      </Button>
                    ) : null}
                  </div>
                </div>
                {collection.description ? (
                  <p className="muted collection-desc">{collection.description}</p>
                ) : null}
              </div>

              {open ? (
                <div className="tree-children">
                  {rootFolders.map((folder) =>
                    renderFolderNode(folder, folders, requests, 1),
                  )}
                  {rootRequests.map((req) => renderRequestRow(req, rootRequests, 1))}
                  {rootFolders.length === 0 && rootRequests.length === 0 ? (
                    <div className="empty">
                      <p>No folders or requests in this collection.</p>
                      {editRequests ? (
                        <Button
                          variant="subtle"
                          size="sm"
                          onClick={() => openCreateRequest(collection.id, null)}
                        >
                          Create request
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <Modal
        open={dialog != null}
        title={dialogTitle}
        onClose={() => !busy && setDialog(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialog(null)} disabled={busy}>
              Cancel
            </Button>
            <Button variant="primary" loading={busy} onClick={() => void submitDialog()}>
              Save
            </Button>
          </>
        }
      >
        {dialog?.type === "create-collection" || dialog?.type === "edit-collection" ? (
          <>
            <Field label="Name">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                placeholder="Collection name"
              />
            </Field>
            <Field label="Description" hint="Optional">
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="What does this collection contain?"
              />
            </Field>
          </>
        ) : null}

        {dialog?.type === "create-folder" || dialog?.type === "edit-folder" ? (
          <>
            <Field label="Name">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                placeholder="Folder name"
              />
            </Field>
            {dialog.type === "edit-folder" ? (
              <Field label="Parent folder" hint="Optional — leave empty for collection root">
                <Select
                  value={parentId}
                  onChange={(e) => setParentId(e.target.value)}
                >
                  <option value="">Collection root</option>
                  {dialog.folders
                    .filter((f) => f.id !== dialog.folder.id)
                    .map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name}
                      </option>
                    ))}
                </Select>
              </Field>
            ) : null}
          </>
        ) : null}

        {dialog?.type === "create-request" ? (
          <Field label="Name">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              placeholder="Request name"
            />
          </Field>
        ) : null}

        {dialog?.type === "edit-request" ? (
          <>
            <Field label="Name">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                placeholder="Request name"
              />
            </Field>
            <Field label="Folder" hint="Optional — leave empty for collection root">
              <Select
                value={parentId}
                onChange={(e) => setParentId(e.target.value)}
              >
                <option value="">Collection root</option>
                {dialog.folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </Select>
            </Field>
          </>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={confirm != null}
        title={
          confirm?.type === "collection"
            ? "Delete collection"
            : confirm?.type === "folder"
              ? "Delete folder"
              : "Delete request"
        }
        message={
          confirm
            ? `Delete "${confirm.name}"? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        danger
        loading={busy}
        onConfirm={() => void confirmDelete()}
        onClose={() => !busy && setConfirm(null)}
      />
    </div>
  );
}
