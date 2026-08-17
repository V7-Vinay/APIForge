import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { ApiError } from "../../api/client";
import { CollaborationClient } from "../../api/collaboration";
import { environmentsApi } from "../../api/environments";
import { executionApi } from "../../api/execution";
import { requestsApi, type RequestPatch } from "../../api/resources";
import { Button } from "../../components/ui/Button";
import { Field, Input, Select, Textarea } from "../../components/ui/Input";
import { CodeBlock, KeyValueEditor } from "../../components/ui/KeyValueEditor";
import { Badge, EmptyState, Spinner, Tabs } from "../../components/ui/Tabs";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import type { AppShellOutletContext } from "../../layouts/AppShell";
import type {
  ApiRequest,
  AuthConfigWrite,
  CollaborationPresence,
  ConnectionState,
  Execution,
  HistoryItem,
  HttpMethod,
  KeyValue,
  RequestAuthType,
} from "../../types/api";
import { HTTP_METHODS } from "../../types/api";
import {
  formatBytes,
  formatDateTime,
  formatDuration,
  formatRelative,
  methodClass,
  statusLabel,
} from "../../utils/format";
import {
  canEditRequests,
  canExecuteRequests,
  canViewHistory,
} from "../../utils/permissions";

export const COMMON_HEADERS = [
  "Accept",
  "Accept-Language",
  "Authorization",
  "Cache-Control",
  "Content-Type",
  "User-Agent",
  "X-Request-Id",
  "X-Api-Key",
];

function cloneKeyValues(items: KeyValue[] | null | undefined): KeyValue[] {
  if (!items || items.length === 0) return [{ key: "", value: "", enabled: true }];
  return items.map((item) => ({ ...item }));
}

function sanitizeKeyValues(items: KeyValue[]): KeyValue[] {
  return items
    .filter((row) => row.key.trim() || row.value.trim())
    .map((row) => ({
      key: row.key,
      value: row.value,
      enabled: row.enabled,
    }));
}

function statusTone(code: number | null | undefined): "success" | "warning" | "danger" | "neutral" {
  if (code == null) return "neutral";
  if (code >= 200 && code < 300) return "success";
  if (code >= 300 && code < 400) return "warning";
  if (code >= 400) return "danger";
  return "neutral";
}

function hasUnmatchedVars(text: string): boolean {
  // After resolve, leftover {{...}} means a variable was missing or unresolved.
  return /\{\{[^}]*\}\}/.test(text) || text.includes("{{") || text.includes("}}");
}

function buildAuthPatch(
  authType: RequestAuthType,
  authToken: string,
  authUsername: string,
  authPassword: string,
  existing: ApiRequest["auth_config"],
): AuthConfigWrite | undefined {
  const prevType = existing?.type ?? "none";

  if (authType === "none") {
    if (prevType !== "none") return { type: "none" };
    return undefined;
  }

  if (authType === "bearer") {
    if (authToken.trim()) {
      return { type: "bearer", token: authToken.trim() };
    }
    // Preserve server secret — never send bearer without a token.
    return undefined;
  }

  if (authType === "basic") {
    if (authPassword) {
      return {
        type: "basic",
        username: authUsername,
        password: authPassword,
      };
    }
    // Preserve server secret — never send basic without a password.
    return undefined;
  }

  return undefined;
}

type Props = {
  request: ApiRequest;
  onRequestChange?: (request: ApiRequest) => void;
};

export default function RequestBuilder({ request, onRequestChange }: Props) {
  const toast = useToast();
  const { token, user } = useAuth();
  const {
    workspace,
    role,
    environments,
    activeEnvironmentId,
    setActiveEnvironmentId,
    upsertRequest,
    foldersByCollection,
  } = useWorkspace();
  const shell = useOutletContext<AppShellOutletContext | undefined>();

  const canEdit = canEditRequests(role);
  const canExecute = canExecuteRequests(role);
  const canHistory = canViewHistory(role);

  const [name, setName] = useState(request.name);
  const [method, setMethod] = useState(request.method);
  const [url, setUrl] = useState(request.url);
  const [headers, setHeaders] = useState<KeyValue[]>(() => cloneKeyValues(request.headers));
  const [params, setParams] = useState<KeyValue[]>(() => cloneKeyValues(request.query_params));
  const [body, setBody] = useState(request.body ?? "");
  const [authType, setAuthType] = useState<RequestAuthType>(
    request.auth_config?.type ?? "none",
  );
  const [authToken, setAuthToken] = useState("");
  const [authUsername, setAuthUsername] = useState(
    request.auth_config?.username ?? "",
  );
  const [authPassword, setAuthPassword] = useState("");
  const [description, setDescription] = useState(request.description ?? "");
  const [folderId, setFolderId] = useState<string | null>(request.folder_id);

  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [execution, setExecution] = useState<Execution | null>(null);
  const [responseTab, setResponseTab] = useState("body");
  const [editorTab, setEditorTab] = useState("params");

  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLimit, setHistoryLimit] = useState(25);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [resolvedUrl, setResolvedUrl] = useState<string | null>(null);
  const [resolveWarning, setResolveWarning] = useState(false);

  const [presence, setPresence] = useState<CollaborationPresence[]>([]);
  const [collabState, setCollabState] = useState<ConnectionState>("DISCONNECTED");
  const collabRef = useRef<CollaborationClient | null>(null);
  const requestRef = useRef(request);
  const dirtyRef = useRef(false);
  requestRef.current = request;
  dirtyRef.current = dirty;

  useEffect(() => {
    shell?.setConnectionState(collabState);
  }, [collabState, shell]);

  useEffect(() => {
    return () => {
      shell?.setConnectionState("DISCONNECTED");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function hydrate(next: ApiRequest) {
    setName(next.name);
    setMethod(next.method);
    setUrl(next.url);
    setHeaders(cloneKeyValues(next.headers));
    setParams(cloneKeyValues(next.query_params));
    setBody(next.body ?? "");
    setAuthType(next.auth_config?.type ?? "none");
    setAuthToken("");
    setAuthUsername(next.auth_config?.username ?? "");
    setAuthPassword("");
    setDescription(next.description ?? "");
    setFolderId(next.folder_id);
    setDirty(false);
  }

  useEffect(() => {
    hydrate(request);
    setExecution(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [request.id]);

  useEffect(() => {
    if (!activeEnvironmentId || !url.includes("{{")) {
      setResolvedUrl(null);
      setResolveWarning(false);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void environmentsApi
        .resolve(activeEnvironmentId, url)
        .then((result) => {
          if (cancelled) return;
          setResolvedUrl(result.resolved_text);
          setResolveWarning(hasUnmatchedVars(result.resolved_text));
        })
        .catch(() => {
          if (!cancelled) {
            setResolvedUrl(null);
            setResolveWarning(false);
          }
        });
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeEnvironmentId, url]);

  useEffect(() => {
    if (!workspace?.id || !token) return;

    const client = new CollaborationClient(
      workspace.id,
      () => token,
      {
        onStateChange: setCollabState,
        onPresence: setPresence,
        onError: (message) => toast.warning(message),
        onEvent: (event) => {
          if (
            event.type === "REQUEST_UPDATED" &&
            (event.request_id === requestRef.current.id ||
              event.resource_id === requestRef.current.id)
          ) {
            void requestsApi
              .get(requestRef.current.id)
              .then((fresh) => {
                upsertRequest(fresh);
                onRequestChange?.(fresh);
                if (!dirtyRef.current) hydrate(fresh);
                else toast.info("Remote update received — save or discard local changes.");
              })
              .catch(() => undefined);
          }
        },
      },
    );
    collabRef.current = client;
    client.connect();
    client.joinRequest(request.id);

    return () => {
      client.leaveRequest(request.id);
      client.disconnect();
      collabRef.current = null;
      setPresence([]);
      setCollabState("DISCONNECTED");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace?.id, token, request.id]);

  useEffect(() => {
    if (editorTab !== "history" || !canHistory) return;
    let cancelled = false;
    setHistoryLoading(true);
    void executionApi
      .history(request.id, historyLimit)
      .then((items) => {
        if (!cancelled) setHistory(items);
      })
      .catch((err) => {
        if (!cancelled) {
          toast.error(err instanceof ApiError ? err.message : "Failed to load history.");
        }
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [editorTab, canHistory, request.id, historyLimit, toast]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const meta = event.metaKey || event.ctrlKey;
      if (!meta) return;
      if (event.key === "Enter") {
        event.preventDefault();
        if (canExecute && !executing) void send();
      }
      if (event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (canEdit && dirty && !saving) void save();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canEdit, canExecute, dirty, saving, executing, name, method, url, headers, params, body, authType, authToken, authUsername, authPassword, description]);

  function markDirty() {
    setDirty(true);
  }

  async function save(): Promise<boolean> {
    if (!canEdit) return false;
    setSaving(true);
    try {
      const patch: RequestPatch = {
        name: name.trim() || "Untitled",
        description: description.trim() || null,
        method,
        url: url.trim(),
        headers: sanitizeKeyValues(headers),
        query_params: sanitizeKeyValues(params),
        body: body.trim() ? body : null,
        folder_id: folderId,
      };

      const authPatch = buildAuthPatch(
        authType,
        authToken,
        authUsername,
        authPassword,
        request.auth_config,
      );
      if (authPatch) {
        patch.auth_config = authPatch;
      } else if (authType === "bearer" && !authToken.trim()) {
        const switchingToBearer = (request.auth_config?.type ?? "none") !== "bearer";
        const missingSavedToken = !request.auth_config?.has_token;
        if (switchingToBearer || missingSavedToken) {
          toast.warning("Enter a bearer token to update auth, or switch Auth to None.");
        }
      } else if (authType === "basic" && !authPassword) {
        const switchingToBasic = (request.auth_config?.type ?? "none") !== "basic";
        const missingSavedPassword = !request.auth_config?.has_credentials;
        if (switchingToBasic || missingSavedPassword) {
          toast.warning("Enter a password to update Basic auth, or switch Auth to None.");
        }
      }

      const updated = await requestsApi.update(request.id, patch);
      upsertRequest(updated);
      onRequestChange?.(updated);
      hydrate(updated);
      toast.success("Request saved");
      return true;
    } catch (err) {
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Save failed.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function send() {
    if (!canExecute) return;
    if (dirty && canEdit) {
      const ok = await save();
      if (!ok) return;
    }
    setExecuting(true);
    setResponseTab("body");
    try {
      const result = await executionApi.execute(
        request.id,
        activeEnvironmentId || null,
      );
      setExecution(result);
      if (!result.success) {
        toast.error(result.error_message || result.error_code || "Request failed.");
      }
      if (canHistory && editorTab === "history") {
        const items = await executionApi.history(request.id, historyLimit);
        setHistory(items);
      }
    } catch (err) {
      setExecution({
        success: false,
        error_code: "CLIENT_ERROR",
        error_message:
          err instanceof ApiError || err instanceof Error
            ? err.message
            : "Execution failed.",
      });
      toast.error(err instanceof ApiError || err instanceof Error ? err.message : "Send failed.");
    } finally {
      setExecuting(false);
    }
  }

  function formatJsonBody() {
    try {
      const pretty = JSON.stringify(JSON.parse(body), null, 2);
      setBody(pretty);
      markDirty();
    } catch {
      toast.warning("Body is not valid JSON.");
    }
  }

  function openHistoryItem(item: HistoryItem) {
    setExecution({
      success: item.success,
      status_code: item.status_code,
      headers: item.response_headers,
      body: item.response_body,
      content_type: item.content_type,
      response_size_bytes: item.response_size_bytes,
      body_is_text: item.response_body != null,
      duration_ms: item.duration_ms,
      error_code: item.error_code,
      error_message: item.error_message,
    });
    setResponseTab("body");
  }

  const presenceNames = presence
    .filter((p) => p.request_id === request.id)
    .map((p) =>
      p.user_id === user?.id ? `${p.name} (you)` : p.name,
    );

  const collabLabel =
    collabState === "CONNECTED"
      ? "live"
      : collabState === "RECONNECTING"
        ? "reconnecting"
        : "offline";

  return (
    <div className="request-builder editor">
      <div className="editor-toolbar">
        <div className="request-meta-row">
          <Field className="request-name-field">
            <Input
              className="request-name"
              value={name}
              readOnly={!canEdit}
              onChange={(e) => {
                setName(e.target.value);
                markDirty();
              }}
              placeholder="Request name"
            />
          </Field>
          {dirty ? <Badge tone="warning">Unsaved</Badge> : null}
        </div>

        <div className="request-line">
          <Select
            value={method}
            disabled={!canEdit}
            onChange={(e) => {
              setMethod(e.target.value as HttpMethod);
              markDirty();
            }}
            aria-label="HTTP method"
          >
            {HTTP_METHODS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
          <Input
            value={url}
            readOnly={!canEdit}
            onChange={(e) => {
              setUrl(e.target.value);
              markDirty();
            }}
            placeholder="https://api.example.com/{{path}}"
            aria-label="Request URL"
          />
          {canEdit ? (
            <Button variant="secondary" loading={saving} onClick={() => void save()}>
              Save
            </Button>
          ) : null}
          {canExecute ? (
            <Button variant="primary" loading={executing} onClick={() => void send()}>
              Send
            </Button>
          ) : null}
        </div>

        <div className="env-row">
          <Field label="Environment">
            <Select
              value={activeEnvironmentId}
              onChange={(e) => setActiveEnvironmentId(e.target.value)}
            >
              <option value="">No environment</option>
              {environments.map((env) => (
                <option key={env.id} value={env.id}>
                  {env.name}
                </option>
              ))}
            </Select>
          </Field>
          {resolvedUrl != null ? (
            <div className="resolved-preview">
              <span className="field-label">Resolved URL</span>
              <code>{resolvedUrl}</code>
              {resolveWarning ? (
                <Badge tone="warning">Unresolved {"{{var}}"}</Badge>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="presence-bar">
          <span
            className={`presence-dot presence-${collabState.toLowerCase()}`}
            title={collabState}
          />
          {presenceNames.length > 0 ? (
            presenceNames.map((label) => (
              <span key={label} className="presence-user">
                {label}
              </span>
            ))
          ) : (
            <span className="muted">No other viewers</span>
          )}
          <small>{collabLabel}</small>
        </div>
      </div>

      <Tabs
        tabs={[
          { id: "params", label: "Params" },
          { id: "headers", label: "Headers" },
          { id: "body", label: "Body" },
          { id: "auth", label: "Auth" },
          ...(canHistory ? [{ id: "history", label: "History" }] : []),
        ]}
        active={editorTab}
        onChange={setEditorTab}
      />

      <div className="editor-panel">
        {editorTab === "params" ? (
          <KeyValueEditor
            items={params}
            onChange={(items) => {
              setParams(items);
              markDirty();
            }}
            readOnly={!canEdit}
            keyPlaceholder="Parameter"
            valuePlaceholder="Value"
          />
        ) : null}

        {editorTab === "headers" ? (
          <KeyValueEditor
            items={headers}
            onChange={(items) => {
              setHeaders(items);
              markDirty();
            }}
            readOnly={!canEdit}
            keyPlaceholder="Header"
            valuePlaceholder="Value"
            suggestions={COMMON_HEADERS}
          />
        ) : null}

        {editorTab === "body" ? (
          <div className="body-editor">
            <div className="panel-actions" style={{ marginBottom: 8 }}>
              {canEdit ? (
                <Button variant="subtle" size="sm" onClick={formatJsonBody}>
                  Format JSON
                </Button>
              ) : null}
            </div>
            <Textarea
              value={body}
              readOnly={!canEdit}
              rows={14}
              placeholder='{"key":"value"}'
              onChange={(e) => {
                setBody(e.target.value);
                markDirty();
              }}
            />
          </div>
        ) : null}

        {editorTab === "auth" ? (
          <div className="auth-editor">
            <Field label="Type">
              <Select
                value={authType}
                disabled={!canEdit}
                onChange={(e) => {
                  setAuthType(e.target.value as RequestAuthType);
                  markDirty();
                }}
              >
                <option value="none">None</option>
                <option value="bearer">Bearer Token</option>
                <option value="basic">Basic Auth</option>
              </Select>
            </Field>

            {authType === "bearer" ? (
              <Field
                label="Token"
                hint={
                  request.auth_config?.has_token
                    ? "A token is saved on the server. Leave blank to keep it."
                    : "Enter a bearer token."
                }
              >
                <Input
                  type="password"
                  autoComplete="off"
                  value={authToken}
                  readOnly={!canEdit}
                  placeholder={
                    request.auth_config?.has_token
                      ? "•••••••• (saved — enter to replace)"
                      : "Enter token"
                  }
                  onChange={(e) => {
                    setAuthToken(e.target.value);
                    markDirty();
                  }}
                />
              </Field>
            ) : null}

            {authType === "basic" ? (
              <>
                <Field label="Username">
                  <Input
                    value={authUsername}
                    readOnly={!canEdit}
                    autoComplete="off"
                    onChange={(e) => {
                      setAuthUsername(e.target.value);
                      markDirty();
                    }}
                  />
                </Field>
                <Field
                  label="Password"
                  hint={
                    request.auth_config?.has_credentials
                      ? "A password is saved on the server. Leave blank to keep it."
                      : "Enter a password."
                  }
                >
                  <Input
                    type="password"
                    autoComplete="off"
                    value={authPassword}
                    readOnly={!canEdit}
                    placeholder={
                      request.auth_config?.has_credentials
                        ? "•••••••• (saved — enter to replace)"
                        : "Enter password"
                    }
                    onChange={(e) => {
                      setAuthPassword(e.target.value);
                      markDirty();
                    }}
                  />
                </Field>
              </>
            ) : null}

            <Field label="Folder" hint="Move this request to another folder in this collection">
              <Select
                value={folderId ?? ""}
                disabled={!canEdit}
                onChange={(e) => {
                  setFolderId(e.target.value || null);
                  markDirty();
                }}
              >
                <option value="">Collection root</option>
                {(foldersByCollection[request.collection_id] ?? []).map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Description" hint="Optional notes for collaborators">
              <Textarea
                value={description}
                readOnly={!canEdit}
                rows={3}
                onChange={(e) => {
                  setDescription(e.target.value);
                  markDirty();
                }}
              />
            </Field>
          </div>
        ) : null}

        {editorTab === "history" && canHistory ? (
          <div className="history-panel">
            {historyLoading && history.length === 0 ? (
              <Spinner label="Loading history" />
            ) : history.length === 0 ? (
              <EmptyState
                title="No execution history"
                description="Send a request to see past responses here."
              />
            ) : (
              <>
                <ul className="history-list">
                  {history.map((item) => (
                    <li key={item.id}>
                      <button
                        type="button"
                        className="history-item"
                        onClick={() => openHistoryItem(item)}
                      >
                        <span className={methodClass(item.method)}>{item.method}</span>
                        <Badge tone={statusTone(item.status_code)}>
                          {item.status_code ?? "—"} {statusLabel(item.status_code)}
                        </Badge>
                        <span className="muted">{formatDuration(item.duration_ms)}</span>
                        <span className="muted">{formatRelative(item.created_at)}</span>
                        <span className="history-url" title={item.url}>
                          {item.url}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
                <Button
                  variant="subtle"
                  size="sm"
                  loading={historyLoading}
                  onClick={() => setHistoryLimit((n) => n + 25)}
                >
                  Load more
                </Button>
              </>
            )}
          </div>
        ) : null}

        {executing ? (
          <div className="notice">
            <Spinner label="Sending request" />
          </div>
        ) : null}

        {execution ? (
          <section className="response-panel">
            <div className="response-head">
              <div className="response-status">
                {execution.success ? (
                  <Badge tone={statusTone(execution.status_code)}>
                    {execution.status_code} {statusLabel(execution.status_code)}
                  </Badge>
                ) : (
                  <Badge tone="danger">
                    {execution.error_code || "Error"}
                  </Badge>
                )}
                <span>{formatDuration(execution.duration_ms)}</span>
                <span>{formatBytes(execution.response_size_bytes)}</span>
              </div>
            </div>

            {!execution.success ? (
              <div className="execution-error">
                {execution.error_message || "The request did not complete successfully."}
              </div>
            ) : (
              <>
                <Tabs
                  tabs={[
                    { id: "body", label: "Body" },
                    { id: "headers", label: "Headers" },
                    { id: "metadata", label: "Metadata" },
                  ]}
                  active={responseTab}
                  onChange={setResponseTab}
                  className="response-tabs"
                />
                <div className="response-body-wrap">
                  {responseTab === "body" ? (
                    execution.body_is_text === false ? (
                      <div className="notice">
                        Binary response
                        {execution.content_type ? ` · ${execution.content_type}` : ""}
                        {execution.response_size_bytes != null
                          ? ` · ${formatBytes(execution.response_size_bytes)}`
                          : ""}
                        . Body preview is omitted.
                      </div>
                    ) : (
                      <CodeBlock
                        value={execution.body}
                        language={
                          (execution.content_type || "").includes("json") ||
                          (execution.body || "").trim().startsWith("{") ||
                          (execution.body || "").trim().startsWith("[")
                            ? "json"
                            : "text"
                        }
                        empty="(empty response)"
                      />
                    )
                  ) : null}
                  {responseTab === "headers" ? (
                    <CodeBlock
                      value={JSON.stringify(execution.headers ?? {}, null, 2)}
                      language="json"
                      empty="No headers"
                    />
                  ) : null}
                  {responseTab === "metadata" ? (
                    <CodeBlock
                      value={JSON.stringify(
                        {
                          status_code: execution.status_code,
                          content_type: execution.content_type,
                          duration_ms: execution.duration_ms,
                          response_size_bytes: execution.response_size_bytes,
                          redirects: execution.redirects,
                          body_is_text: execution.body_is_text,
                          recorded_at: formatDateTime(new Date().toISOString()),
                        },
                        null,
                        2,
                      )}
                      language="json"
                    />
                  ) : null}
                </div>
              </>
            )}
          </section>
        ) : null}
      </div>
    </div>
  );
}
