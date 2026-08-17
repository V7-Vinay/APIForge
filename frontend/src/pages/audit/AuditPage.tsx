import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { auditApi } from "../../api/execution";
import { Button } from "../../components/ui/Button";
import { Badge, EmptyState, Spinner } from "../../components/ui/Tabs";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import type { AuditLog } from "../../types/api";
import { formatDateTime } from "../../utils/format";
import { canViewAudit } from "../../utils/permissions";

function statusTone(code: number): "success" | "warning" | "danger" | "neutral" {
  if (code >= 200 && code < 300) return "success";
  if (code >= 300 && code < 400) return "warning";
  if (code >= 400) return "danger";
  return "neutral";
}

export default function AuditPage() {
  const { workspaceId = "" } = useParams();
  const { role } = useWorkspace();
  const toast = useToast();
  const allowed = canViewAudit(role);

  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);

  const load = useCallback(
    async (beforeId?: string) => {
      const appending = Boolean(beforeId);
      if (appending) setLoadingMore(true);
      else setLoading(true);
      try {
        const batch = await auditApi.list(workspaceId, {
          limit: 50,
          before_id: beforeId,
        });
        setLogs((prev) => (appending ? [...prev, ...batch] : batch));
        setHasMore(batch.length >= 50);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Failed to load audit logs.");
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [toast, workspaceId],
  );

  useEffect(() => {
    if (!allowed) return;
    void load();
  }, [allowed, load]);

  if (!allowed) {
    return (
      <div className="page audit-page">
        <EmptyState
          title="No permission"
          description="Audit logs are available to workspace owners and admins only. Your current role cannot view security activity."
        />
      </div>
    );
  }

  if (loading && logs.length === 0) {
    return <Spinner label="Loading audit logs" />;
  }

  if (!loading && logs.length === 0) {
    return (
      <div className="page audit-page">
        <EmptyState
          title="No audit events"
          description="No recorded activity yet for this workspace."
          action={
            <Button variant="secondary" onClick={() => void load()}>
              Refresh
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="page audit-page">
      <div className="explorer-toolbar">
        <h2>Audit log</h2>
        <Button variant="ghost" size="sm" onClick={() => void load()}>
          Refresh
        </Button>
      </div>

      <div className="audit-table-wrap">
        <table className="audit-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>User</th>
              <th>Action</th>
              <th>Method</th>
              <th>Path</th>
              <th>Status</th>
              <th>Resource</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id} className="audit-row">
                <td>{formatDateTime(log.created_at)}</td>
                <td>
                  <code>{log.user_id ?? "—"}</code>
                </td>
                <td>
                  <strong>{log.action}</strong>
                </td>
                <td>{log.method}</td>
                <td>
                  <code title={log.path}>{log.path}</code>
                </td>
                <td>
                  <Badge tone={statusTone(log.status_code)}>{log.status_code}</Badge>
                </td>
                <td>
                  {log.resource_type
                    ? `${log.resource_type}${log.resource_id ? `:${log.resource_id.slice(0, 8)}` : ""}`
                    : "—"}
                </td>
                <td>
                  <small>{log.ip_address ?? "—"}</small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasMore ? (
        <div className="panel-actions" style={{ marginTop: 12 }}>
          <Button
            variant="secondary"
            loading={loadingMore}
            onClick={() => {
              const last = logs[logs.length - 1];
              if (last) void load(last.id);
            }}
          >
            Load more
          </Button>
        </div>
      ) : null}
    </div>
  );
}
