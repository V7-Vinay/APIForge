import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { documentationApi } from "../../api/execution";
import { Button } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Input";
import { Badge, EmptyState, Panel, Spinner } from "../../components/ui/Tabs";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import type { DocumentationSummary, OpenAPIImportResult } from "../../types/api";
import { hasPermission } from "../../utils/permissions";

export default function DocumentationPage() {
  const { workspaceId = "" } = useParams();
  const toast = useToast();
  const { role, refreshTree } = useWorkspace();
  const canEdit = hasPermission(role, "documentation:edit");

  const [summary, setSummary] = useState<DocumentationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [collectionName, setCollectionName] = useState("");
  const [importResult, setImportResult] = useState<OpenAPIImportResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadSummary() {
    setLoading(true);
    try {
      const data = await documentationApi.summary(workspaceId);
      setSummary(data);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load documentation.");
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId]);

  async function exportOpenApi() {
    setExporting(true);
    try {
      await documentationApi.exportOpenApi(workspaceId, "apiforge-openapi.json");
      toast.success("OpenAPI exported");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  async function onFileSelected(file: File | null) {
    if (!file || !canEdit) return;
    setImporting(true);
    setImportResult(null);
    try {
      const text = await file.text();
      let spec: Record<string, unknown>;
      try {
        spec = JSON.parse(text) as Record<string, unknown>;
      } catch {
        throw new Error("Selected file is not valid JSON.");
      }
      if (!spec || typeof spec !== "object" || Array.isArray(spec)) {
        throw new Error("OpenAPI spec must be a JSON object.");
      }
      const result = await documentationApi.importOpenApi(
        workspaceId,
        spec,
        collectionName.trim() || undefined,
      );
      setImportResult(result);
      toast.success(`Imported "${result.collection_name}"`);
      await refreshTree();
      await loadSummary();
      setCollectionName("");
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      toast.error(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Import failed.",
      );
    } finally {
      setImporting(false);
    }
  }

  if (loading && !summary) {
    return <Spinner label="Loading documentation" />;
  }

  if (!summary) {
    return (
      <EmptyState
        title="Documentation unavailable"
        description="Could not load documentation summary for this workspace."
        action={
          <Button variant="secondary" onClick={() => void loadSummary()}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="page documentation-page">
      <Panel
        title={summary.title || "API Documentation"}
        actions={
          <Button variant="secondary" loading={exporting} onClick={() => void exportOpenApi()}>
            Export OpenAPI
          </Button>
        }
      >
        <p className="muted">Version {summary.version || "—"}</p>
        <div className="doc-stats">
          <div className="doc-stat">
            <Badge tone="info">{summary.collection_count}</Badge>
            <span>Collections</span>
          </div>
          <div className="doc-stat">
            <Badge tone="info">{summary.folder_count}</Badge>
            <span>Folders</span>
          </div>
          <div className="doc-stat">
            <Badge tone="info">{summary.request_count}</Badge>
            <span>Requests</span>
          </div>
        </div>
      </Panel>

      <Panel title="Import OpenAPI" className="documentation-panel">
        {canEdit ? (
          <>
            <p className="muted">
              Upload an OpenAPI 3.x JSON document to create a collection with folders and
              requests.
            </p>
            <Field label="Collection name" hint="Optional override for the imported collection">
              <Input
                value={collectionName}
                onChange={(e) => setCollectionName(e.target.value)}
                placeholder="Imported API"
              />
            </Field>
            <div className="documentation-actions">
              <label className="file-button">
                Choose JSON file
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/json,.json"
                  hidden
                  disabled={importing}
                  onChange={(e) => void onFileSelected(e.target.files?.[0] ?? null)}
                />
              </label>
              {importing ? <Spinner label="Importing" /> : null}
            </div>
            {importResult ? (
              <div className="notice">
                Imported <strong>{importResult.collection_name}</strong>
                {" · "}
                {importResult.folder_count} folders
                {" · "}
                {importResult.request_count} requests
              </div>
            ) : null}
          </>
        ) : (
          <p className="muted">
            You need documentation edit permission to import OpenAPI specifications.
          </p>
        )}
      </Panel>
    </div>
  );
}
