import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { searchApi } from "../../api/execution";
import { Button } from "../../components/ui/Button";
import { Field, Input, Select } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { Badge, EmptyState, Spinner } from "../../components/ui/Tabs";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import type { SearchItem } from "../../types/api";
import { HTTP_METHODS } from "../../types/api";
import { methodClass } from "../../utils/format";

type Props = {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

export default function CommandPalette({ open: controlledOpen, onOpenChange }: Props) {
  const { workspaceId: routeWorkspaceId } = useParams();
  const { workspace } = useWorkspace();
  const workspaceId = routeWorkspaceId || workspace?.id || "";
  const navigate = useNavigate();
  const toast = useToast();

  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;

  const setOpen = useCallback(
    (value: boolean) => {
      onOpenChange?.(value);
      if (controlledOpen === undefined) setInternalOpen(value);
    },
    [controlledOpen, onOpenChange],
  );

  const [query, setQuery] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [method, setMethod] = useState("");
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<SearchItem[]>([]);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const meta = event.metaKey || event.ctrlKey;
      if (meta && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  useEffect(() => {
    if (!open || !workspaceId) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      void searchApi
        .search(workspaceId, {
          q: query.trim() || undefined,
          resource_type: resourceType || undefined,
          method: method || undefined,
          page,
          page_size: 20,
          sort_by: sortBy,
          sort_order: sortOrder,
        })
        .then((result) => {
          if (cancelled) return;
          setItems(result.items);
          setHasNext(result.has_next);
          setHasPrevious(result.has_previous);
          setTotal(result.total);
        })
        .catch((err) => {
          if (cancelled) return;
          toast.error(err instanceof ApiError ? err.message : "Search failed.");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, query ? 200 : 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    open,
    workspaceId,
    query,
    resourceType,
    method,
    page,
    sortBy,
    sortOrder,
    toast,
  ]);

  useEffect(() => {
    if (open) {
      setPage(1);
    } else {
      setQuery("");
      setItems([]);
    }
  }, [open]);

  function selectItem(item: SearchItem) {
    setOpen(false);
    if (item.resource_type === "request") {
      navigate(`/workspaces/${workspaceId}/requests/${item.id}`);
      return;
    }
    if (item.resource_type === "collection") {
      navigate(`/workspaces/${workspaceId}/collections`);
      return;
    }
    // folder → collections explorer
    navigate(`/workspaces/${workspaceId}/collections`);
  }

  return (
    <Modal
      open={open}
      title="Search workspace"
      size="lg"
      onClose={() => setOpen(false)}
      footer={
        <div className="palette-footer">
          <span className="muted">{total} results</span>
          <div className="panel-actions">
            <Button
              variant="ghost"
              size="sm"
              disabled={!hasPrevious || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={!hasNext || loading}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      }
    >
      <div className="command-palette">
        <Field label="Query">
          <Input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search collections, folders, requests…"
            autoFocus
          />
        </Field>

        <div className="palette-filters">
          <Field label="Type">
            <Select
              value={resourceType}
              onChange={(e) => {
                setResourceType(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All</option>
              <option value="collection">Collection</option>
              <option value="folder">Folder</option>
              <option value="request">Request</option>
            </Select>
          </Field>
          <Field label="Method">
            <Select
              value={method}
              onChange={(e) => {
                setMethod(e.target.value);
                setPage(1);
              }}
            >
              <option value="">Any</option>
              {HTTP_METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Sort">
            <Select
              value={`${sortBy}:${sortOrder}`}
              onChange={(e) => {
                const [by, order] = e.target.value.split(":");
                setSortBy(by);
                setSortOrder(order);
                setPage(1);
              }}
            >
              <option value="updated_at:desc">Recently updated</option>
              <option value="updated_at:asc">Oldest updated</option>
              <option value="name:asc">Name A–Z</option>
              <option value="name:desc">Name Z–A</option>
              <option value="created_at:desc">Newest</option>
              <option value="created_at:asc">Oldest</option>
              <option value="position:asc">Position</option>
            </Select>
          </Field>
        </div>

        {loading && items.length === 0 ? (
          <Spinner label="Searching" />
        ) : items.length === 0 ? (
          <EmptyState
            title="No matches"
            description="Try a different query or clear filters."
          />
        ) : (
          <ul className="search-results-list">
            {items.map((item) => (
              <li key={`${item.resource_type}-${item.id}`}>
                <button
                  type="button"
                  className="search-result-item"
                  onClick={() => selectItem(item)}
                >
                  <div className="search-result-main">
                    <Badge tone="neutral">{item.resource_type}</Badge>
                    {item.method ? (
                      <span className={methodClass(item.method)}>{item.method}</span>
                    ) : null}
                    <strong>{item.name}</strong>
                  </div>
                  {item.url ? <small>{item.url}</small> : null}
                  {item.description ? <small>{item.description}</small> : null}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Modal>
  );
}
