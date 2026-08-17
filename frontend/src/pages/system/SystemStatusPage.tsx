import { useCallback, useEffect, useState } from "react";
import { systemApi } from "../../api/execution";
import { ApiError, apiRaw } from "../../api/client";
import { useToast } from "../../contexts/ToastContext";
import { Button } from "../../components/ui/Button";
import { Badge, Panel, Spinner } from "../../components/ui/Tabs";
import type { AppInfo, HealthResponse, ReadyResponse } from "../../types/api";

function statusTone(
  value: string | undefined,
): "success" | "warning" | "danger" | "neutral" {
  if (!value) return "neutral";
  const v = value.toLowerCase();
  if (
    v === "ok" ||
    v === "healthy" ||
    v === "ready" ||
    v === "up" ||
    v === "true"
  ) {
    return "success";
  }
  if (v === "degraded" || v === "starting") return "warning";
  return "danger";
}

function normalizeReady(payload: unknown): ReadyResponse | null {
  if (!payload || typeof payload !== "object") return null;
  const record = payload as Record<string, unknown>;
  const detail =
    record.detail && typeof record.detail === "object"
      ? (record.detail as Record<string, unknown>)
      : record;
  if (!("postgres" in detail) && !("redis" in detail)) return null;
  return {
    status: String(detail.status ?? "not_ready"),
    postgres:
      detail.postgres === true || detail.postgres === "ok"
        ? "ok"
        : detail.postgres === false
          ? "down"
          : String(detail.postgres ?? "unknown"),
    redis:
      detail.redis === true || detail.redis === "ok"
        ? "ok"
        : detail.redis === false
          ? "down"
          : String(detail.redis ?? "unknown"),
  };
}

async function fetchReady(): Promise<ReadyResponse> {
  const response = await apiRaw("/ready", {}, false);
  const body = await response.json().catch(() => null);
  if (response.ok) {
    const parsed = normalizeReady(body);
    if (parsed) return parsed;
    return body as ReadyResponse;
  }
  const parsed = normalizeReady(body);
  if (parsed) return parsed;
  throw new ApiError(
    (body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof (body as { detail: unknown }).detail === "string"
      ? (body as { detail: string }).detail
      : null) ?? `Ready check failed (${response.status}).`,
    response.status,
  );
}

export function SystemStatusPage() {
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    const nextErrors: string[] = [];
    const [healthResult, readyResult, infoResult] = await Promise.allSettled([
      systemApi.health(),
      fetchReady(),
      systemApi.info(),
    ]);

    if (healthResult.status === "fulfilled") {
      setHealth(healthResult.value);
    } else {
      setHealth(null);
      nextErrors.push(
        healthResult.reason instanceof ApiError
          ? `Health: ${healthResult.reason.message}`
          : "Health: unavailable",
      );
    }

    if (readyResult.status === "fulfilled") {
      setReady(readyResult.value);
      if (readyResult.value.status !== "ready") {
        nextErrors.push("Ready: dependencies not fully ready.");
      }
    } else {
      setReady(null);
      nextErrors.push(
        readyResult.reason instanceof ApiError
          ? `Ready: ${readyResult.reason.message}`
          : "Ready: unavailable",
      );
    }

    if (infoResult.status === "fulfilled") {
      setInfo(infoResult.value);
    } else {
      setInfo(null);
      nextErrors.push(
        infoResult.reason instanceof Error
          ? `Info: ${infoResult.reason.message}`
          : "Info: unavailable",
      );
    }

    setErrors(nextErrors);
    if (nextErrors.length) {
      toast.warning("Some system checks reported issues.");
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const backendStatus =
    health?.status ??
    (errors.some((e) => e.startsWith("Health")) ? "down" : "unknown");
  const postgresStatus = ready?.postgres ?? "unknown";
  const redisStatus = ready?.redis ?? "unknown";

  return (
    <div className="page system-status-page">
      <header className="page-header">
        <div>
          <h1>System status</h1>
          <p>Backend health, readiness, and application identity.</p>
        </div>
        <Button
          variant="secondary"
          onClick={() => void load()}
          disabled={loading}
        >
          Refresh
        </Button>
      </header>

      {loading && !health && !ready && !info ? (
        <div className="page-loading">
          <Spinner label="Checking system" />
        </div>
      ) : (
        <>
          <div className="stat-row">
            <Panel title="Backend">
              <div className="status-block">
                <Badge tone={statusTone(backendStatus)}>{backendStatus}</Badge>
                {health?.service ? (
                  <span className="muted">{health.service}</span>
                ) : null}
                {health?.version ? (
                  <span className="muted">v{health.version}</span>
                ) : null}
              </div>
            </Panel>
            <Panel title="Database">
              <div className="status-block">
                <Badge tone={statusTone(postgresStatus)}>
                  {postgresStatus}
                </Badge>
                <span className="muted">PostgreSQL</span>
              </div>
            </Panel>
            <Panel title="Redis">
              <div className="status-block">
                <Badge tone={statusTone(redisStatus)}>{redisStatus}</Badge>
                <span className="muted">Cache / realtime</span>
              </div>
            </Panel>
          </div>

          <Panel title="Application info">
            {info ? (
              <dl className="detail-list">
                <div>
                  <dt>Name</dt>
                  <dd>{info.name}</dd>
                </div>
                <div>
                  <dt>Version</dt>
                  <dd>{info.version}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>
                    <Badge tone={statusTone(info.status)}>{info.status}</Badge>
                  </dd>
                </div>
                {info.build_sha ? (
                  <div>
                    <dt>Build</dt>
                    <dd>
                      <code>{info.build_sha}</code>
                    </dd>
                  </div>
                ) : null}
              </dl>
            ) : (
              <p className="muted">Application info could not be loaded.</p>
            )}
          </Panel>

          {errors.length > 0 ? (
            <Panel title="Errors" className="danger-panel">
              <ul className="error-list">
                {errors.map((err) => (
                  <li key={err}>{err}</li>
                ))}
              </ul>
            </Panel>
          ) : null}
        </>
      )}
    </div>
  );
}
