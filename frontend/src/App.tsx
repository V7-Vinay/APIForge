import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type User = { id: string; name: string; email: string; created_at: string };
type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};
type Workspace = { id: string; name: string; slug: string };
type Collection = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  position: number;
};
type Folder = {
  id: string;
  collection_id: string;
  parent_id: string | null;
  name: string;
  position: number;
};
type Environment = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};
type EnvironmentVariable = {
  id: string;
  environment_id: string;
  key: string;
  is_secret: boolean;
  created_at: string;
  updated_at: string;
};
type SearchItem = {
  id: string;
  resource_type: "collection" | "folder" | "request";
  name: string;
  description: string | null;
  collection_id: string | null;
  folder_id: string | null;
  method: string | null;
  url: string | null;
  position: number;
  created_at: string;
  updated_at: string;
};
type APIRequest = {
  id: string;
  collection_id: string;
  folder_id: string | null;
  name: string;
  description: string | null;
  method: string;
  url: string;
  headers: { key: string; value: string; enabled: boolean }[] | null;
  query_params: { key: string; value: string; enabled: boolean }[] | null;
  body: string | null;
  auth_config: {
    type: string;
    token?: string;
    username?: string;
    password?: string;
    has_credentials?: boolean;
    has_token?: boolean;
  } | null;
  position: number;
};

type CollaborationPresence = {
  connection_id: string;
  user_id: string;
  name: string;
  request_id: string;
  last_seen: string;
};

type CollaborationEvent = {
  type: string;
  actor_id?: string | null;
  request_id?: string | null;
  resource_id?: string | null;
  resource_type?: string | null;
  payload?: Record<string, any>;
};

type AuditLog = {
  id: string;
  user_id: string | null;
  workspace_id: string | null;
  action: string;
  method: string;
  path: string;
  status_code: number;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  metadata_json: Record<string, any>;
  created_at: string;
};

let tokenRefreshHandler: ((newToken: string) => void) | null = null;
let logoutHandler: (() => void) | null = null;

async function api<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
  isRetry = false,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  if (
    response.status === 401 &&
    !isRetry &&
    path !== "/auth/refresh" &&
    path !== "/auth/login" &&
    path !== "/auth/register"
  ) {
    try {
      const refreshResult = await api<{ access_token: string }>(
        "/auth/refresh",
        { method: "POST" },
        undefined,
        true,
      );
      const newToken = refreshResult.access_token;
      if (tokenRefreshHandler) {
        tokenRefreshHandler(newToken);
      }
      return await api<T>(path, options, newToken, true);
    } catch (refreshErr) {
      if (logoutHandler) {
        logoutHandler();
      }
      throw refreshErr;
    }
  }
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      body?.error?.message ??
        body?.detail ??
        `Request failed (${response.status})`,
    );
  return body as T;
}

export default function App() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [message, setMessage] = useState("");
  const [executing, setExecuting] = useState(false);
  const [execution, setExecution] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [collections, setCollections] = useState<Collection[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [requests, setRequests] = useState<APIRequest[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchItem[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [environmentId, setEnvironmentId] = useState("");
  const [variables, setVariables] = useState<EnvironmentVariable[]>([]);
  const [selectedCollection, setSelectedCollection] =
    useState<Collection | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<APIRequest | null>(
    null,
  );
  const [requestName, setRequestName] = useState("");
  const [method, setMethod] = useState("GET");
  const [url, setUrl] = useState("");
  const [body, setBody] = useState("");

  const [activeTab, setActiveTab] = useState<
    "params" | "headers" | "body" | "auth"
  >("body");
  const [authType, setAuthType] = useState("none");
  const [authUsername, setAuthUsername] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authToken, setAuthToken] = useState("");

  const [collaborationSocket, setCollaborationSocket] =
    useState<WebSocket | null>(null);
  const [collaborationReady, setCollaborationReady] = useState(false);
  const [presence, setPresence] = useState<
    Record<string, CollaborationPresence>
  >({});
  const [documentationOpen, setDocumentationOpen] = useState(false);
  const [documentationSummary, setDocumentationSummary] = useState<{
    title: string;
    version: string;
    collection_count: number;
    folder_count: number;
    request_count: number;
  } | null>(null);
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const selectedRequestRef = useRef<APIRequest | null>(null);
  const selectedCollectionRef = useRef<Collection | null>(null);
  const userRef = useRef<User | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          body: JSON.stringify({ name, email, password }),
        });
        setMode("login");
        setMessage("Account created. Log in to continue.");
        return;
      }
      const auth = await api<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      const me = await api<User>("/auth/me", {}, auth.access_token);
      setToken(auth.access_token);
      setUser(me);
      await loadWorkspaces(auth.access_token);
      setMessage("Authenticated successfully.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function loadWorkspaces(accessToken = token!) {
    const data = await api<Workspace[]>("/workspaces", {}, accessToken);
    setWorkspaces(data);
    if (!workspaceId && data[0]) {
      setWorkspaceId(data[0].id);
      await Promise.all([
        loadCollections(data[0].id, accessToken),
        loadEnvironments(data[0].id, accessToken),
      ]);
    }
  }

  async function loadEnvironments(id = workspaceId, accessToken = token!) {
    if (!id) return;
    const data = await api<Environment[]>(
      `/workspaces/${id}/environments`,
      {},
      accessToken,
    );
    setEnvironments(data);
    if (!environmentId && data[0]) {
      setEnvironmentId(data[0].id);
      await loadVariables(data[0].id, accessToken);
    }
  }

  async function loadVariables(id = environmentId, accessToken = token!) {
    if (!id) return;
    const data = await api<EnvironmentVariable[]>(
      `/environments/${id}/variables`,
      {},
      accessToken,
    );
    setVariables(data);
  }

  async function createEnvironment() {
    if (!token || !workspaceId) return;
    const name = window.prompt("Environment name");
    if (!name) return;
    try {
      const created = await api<Environment>(
        `/workspaces/${workspaceId}/environments`,
        { method: "POST", body: JSON.stringify({ name }) },
        token,
      );
      setEnvironments((prev) => [...prev, created]);
      setEnvironmentId(created.id);
      setVariables([]);
      setMessage("Environment created.");
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Could not create environment.",
      );
    }
  }

  async function createVariable() {
    if (!token || !environmentId) return;
    const key = window.prompt("Variable key");
    if (!key) return;
    const value = window.prompt(`Value for ${key}`);
    if (value === null) return;
    try {
      const created = await api<EnvironmentVariable>(
        `/environments/${environmentId}/variables`,
        {
          method: "POST",
          body: JSON.stringify({ key, value, is_secret: false }),
        },
        token,
      );
      setVariables((prev) => [...prev, created]);
      setMessage("Variable created.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not create variable.");
    }
  }

  async function runSearch(query = searchQuery) {
    if (!token || !workspaceId) return;
    const trimmed = query.trim();
    if (!trimmed) {
      setSearchResults([]);
      return;
    }
    try {
      const result = await api<{ items: SearchItem[]; total: number }>(
        `/workspaces/${workspaceId}/search?q=${encodeURIComponent(trimmed)}&page=1&page_size=12&sort_by=name&sort_order=asc`,
        {},
        token,
      );
      setSearchResults(result.items);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Search failed.");
    }
  }

  async function selectSearchResult(item: SearchItem) {
    if (!token || !item.collection_id) return;
    const collection = collections.find((c) => c.id === item.collection_id);
    if (collection) {
      setSelectedCollection(collection);
      await loadChildren(collection.id, token);
      if (item.resource_type === "request") {
        const request = await api<APIRequest>(
          `/requests/${item.id}`,
          {},
          token,
        );
        setSelectedRequest(request);
      }
    }
    setSearchQuery("");
    setSearchResults([]);
  }

  async function loadCollections(id = workspaceId, accessToken = token!) {
    if (!id) return;
    const data = await api<Collection[]>(
      `/workspaces/${id}/collections`,
      {},
      accessToken,
    );
    setCollections(data);
    setSelectedCollection(data[0] ?? null);
    if (data[0]) await loadChildren(data[0].id, accessToken);
  }

  async function loadChildren(collectionId: string, accessToken = token!) {
    const [f, r] = await Promise.all([
      api<Folder[]>(`/collections/${collectionId}/folders`, {}, accessToken),
      api<APIRequest[]>(
        `/collections/${collectionId}/requests`,
        {},
        accessToken,
      ),
    ]);
    setFolders(f);
    setRequests(r);
    setSelectedRequest(r[0] ?? null);
  }

  useEffect(() => {
    tokenRefreshHandler = (newToken) => {
      setToken(newToken);
    };
    logoutHandler = () => {
      logout();
    };
    return () => {
      tokenRefreshHandler = null;
      logoutHandler = null;
    };
  }, []);

  useEffect(() => {
    selectedRequestRef.current = selectedRequest;
    if (selectedRequest) {
      setRequestName(selectedRequest.name);
      setMethod(selectedRequest.method);
      setUrl(selectedRequest.url);
      setBody(selectedRequest.body ?? "");

      const auth = selectedRequest.auth_config || { type: "none" };
      setAuthType(auth.type || "none");
      setAuthUsername(auth.username || "");
      setAuthPassword("");
      setAuthToken("");
    }
  }, [selectedRequest]);

  useEffect(() => {
    selectedCollectionRef.current = selectedCollection;
  }, [selectedCollection]);

  useEffect(() => {
    userRef.current = user;
  }, [user]);

  useEffect(() => {
    if (!token || !workspaceId) {
      setCollaborationReady(false);
      setPresence({});
      collaborationSocket?.close();
      setCollaborationSocket(null);
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(
      `${protocol}//${window.location.host}/api/v1/workspaces/${workspaceId}/collaboration`,
    );
    setCollaborationSocket(socket);
    setCollaborationReady(false);

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: "AUTH", token }));
    };

    socket.onmessage = async (message) => {
      const event = JSON.parse(message.data) as CollaborationEvent;
      const payload = event.payload ?? {};

      if (event.type === "AUTHENTICATED" && payload.connection_id) {
        setCollaborationReady(true);
        return;
      }

      if (event.type === "PRESENCE_SNAPSHOT") {
        const next: Record<string, CollaborationPresence> = {};
        for (const item of (payload.users ?? []) as CollaborationPresence[]) {
          next[item.connection_id] = item;
        }
        setPresence(next);
        return;
      }

      if (event.type === "USER_JOINED_REQUEST") {
        if (event.request_id !== selectedRequestRef.current?.id) return;
        const joined = payload as Partial<CollaborationPresence>;
        const connectionId = joined.connection_id;
        const joinedUserId = joined.user_id;
        const joinedName =
          joined.name ?? (payload.user_name as string | undefined);
        const joinedRequestId = event.request_id;
        if (connectionId && joinedUserId && joinedName && joinedRequestId) {
          setPresence((prev) => ({
            ...prev,
            [connectionId]: {
              connection_id: connectionId,
              user_id: joinedUserId,
              name: joinedName,
              request_id: joinedRequestId,
              last_seen: new Date().toISOString(),
            },
          }));
        }
        return;
      }

      if (event.type === "USER_LEFT_REQUEST") {
        if (event.request_id !== selectedRequestRef.current?.id) return;
        setPresence((prev) => {
          const next = { ...prev };
          for (const [key, item] of Object.entries(next)) {
            if (
              item.user_id === event.actor_id &&
              item.request_id === event.request_id
            ) {
              delete next[key];
            }
          }
          return next;
        });
        return;
      }

      if (
        event.type === "REQUEST_UPDATED" &&
        event.actor_id !== userRef.current?.id
      ) {
        const action = payload.action;
        if (event.request_id === selectedRequestRef.current?.id) {
          if (action === "deleted") {
            setSelectedRequest(null);
          } else {
            try {
              const refreshed = await api<APIRequest>(
                `/requests/${event.request_id}`,
                {},
                token,
              );
              setSelectedRequest(refreshed);
              setRequests((prev) =>
                prev.map((r) => (r.id === refreshed.id ? refreshed : r)),
              );
            } catch {
              setSelectedRequest(null);
            }
          }
        }
        const activeCollectionId = selectedCollectionRef.current?.id;
        if (
          activeCollectionId &&
          activeCollectionId === payload.collection_id
        ) {
          await loadChildren(activeCollectionId, token);
        }
        return;
      }

      if (
        event.type === "COLLECTION_UPDATED" &&
        event.actor_id !== userRef.current?.id
      ) {
        if (event.resource_type === "collection") {
          await loadCollections(workspaceId, token);
        } else {
          const activeCollectionId = selectedCollectionRef.current?.id;
          if (
            activeCollectionId &&
            activeCollectionId === payload.collection_id
          ) {
            await loadChildren(activeCollectionId, token);
          }
        }
      }
    };

    socket.onclose = () => {
      setCollaborationReady(false);
      setPresence({});
    };

    return () => {
      socket.close();
      setCollaborationReady(false);
      setPresence({});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, workspaceId]);

  useEffect(() => {
    if (!collaborationSocket || !collaborationReady || !selectedRequest) return;
    collaborationSocket.send(
      JSON.stringify({ type: "JOIN_REQUEST", request_id: selectedRequest.id }),
    );
    const heartbeat = window.setInterval(() => {
      if (collaborationSocket.readyState === WebSocket.OPEN) {
        collaborationSocket.send(JSON.stringify({ type: "PING" }));
      }
    }, 10000);
    return () => {
      window.clearInterval(heartbeat);
      if (collaborationSocket.readyState === WebSocket.OPEN) {
        collaborationSocket.send(JSON.stringify({ type: "LEAVE_REQUEST" }));
      }
      setPresence({});
    };
  }, [collaborationSocket, collaborationReady, selectedRequest?.id]);

  async function updateAuthConfig() {
    if (!token || !selectedRequest) return;
    try {
      const auth_config: any = { type: authType };
      if (authType === "bearer") {
        if (authToken) {
          auth_config.token = authToken;
        } else if (
          selectedRequest.auth_config?.type === "bearer" &&
          selectedRequest.auth_config?.has_token
        ) {
          alert("Please enter a new token value to update.");
          return;
        } else {
          alert("Bearer token is required.");
          return;
        }
      } else if (authType === "basic") {
        auth_config.username = authUsername;
        if (authPassword) {
          auth_config.password = authPassword;
        } else if (
          selectedRequest.auth_config?.type === "basic" &&
          selectedRequest.auth_config?.has_credentials
        ) {
          alert("Please enter a new password value to update.");
          return;
        } else {
          alert("Password is required.");
          return;
        }
      }
      const updated = await api<APIRequest>(
        `/requests/${selectedRequest.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            auth_config,
          }),
        },
        token,
      );
      setSelectedRequest(updated);
      setRequests((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r)),
      );
      setMessage("Authentication updated successfully.");
      setAuthPassword("");
      setAuthToken("");
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Could not update credentials.",
      );
    }
  }

  async function createCollection() {
    const name = window.prompt("Collection name");
    if (!name || !token || !workspaceId) return;
    try {
      await api<Collection>(
        `/workspaces/${workspaceId}/collections`,
        { method: "POST", body: JSON.stringify({ name }) },
        token,
      );
      await loadCollections(workspaceId, token);
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Could not create collection.",
      );
    }
  }

  async function createRequest() {
    if (!token || !selectedCollection) return;
    try {
      const created = await api<APIRequest>(
        `/collections/${selectedCollection.id}/requests`,
        {
          method: "POST",
          body: JSON.stringify({
            name: "New Request",
            method: "GET",
            url: "https://example.com",
            headers: [],
            query_params: [],
            body: null,
            auth_config: { type: "none" },
          }),
        },
        token,
      );
      setRequests((prev) => [...prev, created]);
      setSelectedRequest(created);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not create request.");
    }
  }

  async function createFolder() {
    if (!token || !selectedCollection) return;
    const name = window.prompt("Folder name");
    if (!name) return;
    try {
      const created = await api<Folder>(
        `/collections/${selectedCollection.id}/folders`,
        { method: "POST", body: JSON.stringify({ name, parent_id: null }) },
        token,
      );
      setFolders((prev) => [...prev, created]);
      setMessage("Folder created.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not create folder.");
    }
  }

  async function deleteCollection() {
    if (
      !token ||
      !selectedCollection ||
      !window.confirm(`Delete collection '${selectedCollection.name}'?`)
    )
      return;
    try {
      await api(
        `/collections/${selectedCollection.id}`,
        { method: "DELETE" },
        token,
      );
      await loadCollections(workspaceId, token);
      setSelectedRequest(null);
      setMessage("Collection deleted.");
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Could not delete collection.",
      );
    }
  }

  async function deleteRequest() {
    if (
      !token ||
      !selectedRequest ||
      !window.confirm(`Delete request '${selectedRequest.name}'?`)
    )
      return;
    try {
      await api(`/requests/${selectedRequest.id}`, { method: "DELETE" }, token);
      const remaining = requests.filter((r) => r.id !== selectedRequest.id);
      setRequests(remaining);
      setSelectedRequest(remaining[0] ?? null);
      setMessage("Request deleted.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not delete request.");
    }
  }

  async function executeSelectedRequest() {
    if (!token || !selectedRequest || !environmentId) {
      setMessage("Select an environment before sending.");
      return;
    }
    setExecuting(true);
    setExecution(null);
    setMessage("");
    try {
      const result = await api<any>(
        `/requests/${selectedRequest.id}/execute`,
        {
          method: "POST",
          body: JSON.stringify({ environment_id: environmentId }),
        },
        token,
      );
      setExecution(result);
      if (!result.success)
        setMessage(result.error_message || "Execution failed.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Execution failed.");
    } finally {
      setExecuting(false);
    }
  }

  async function saveRequest(event: FormEvent) {
    event.preventDefault();
    if (!token || !selectedRequest) return;
    try {
      const updated = await api<APIRequest>(
        `/requests/${selectedRequest.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            name: requestName,
            method,
            url,
            body: body || null,
          }),
        },
        token,
      );
      setSelectedRequest(updated);
      setRequests((prev) =>
        prev.map((r) => (r.id === updated.id ? updated : r)),
      );
      setMessage("Request saved.");
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not save request.");
    }
  }

  async function loadDocumentationSummary() {
    if (!token || !workspaceId) return;
    try {
      const summary = await api<{
        title: string;
        version: string;
        collection_count: number;
        folder_count: number;
        request_count: number;
      }>(`/workspaces/${workspaceId}/documentation/summary`, {}, token);
      setDocumentationSummary(summary);
    } catch (e) {
      setMessage(
        e instanceof Error
          ? e.message
          : "Could not load documentation summary.",
      );
    }
  }

  async function loadAuditLogs() {
    if (!token || !workspaceId) return;
    try {
      const data = await api<AuditLog[]>(
        `/workspaces/${workspaceId}/audit-logs?limit=50`,
        {},
        token,
      );
      setAuditLogs(data);
    } catch (e) {
      setAuditLogs([]);
      setMessage(e instanceof Error ? e.message : "Could not load audit logs.");
    }
  }

  async function exportOpenAPI() {
    if (!token || !workspaceId) return;
    try {
      const response = await fetch(
        `/api/v1/workspaces/${workspaceId}/documentation/openapi.json`,
        {
          headers: { Authorization: `Bearer ${token}` },
          credentials: "include",
        },
      );
      if (!response.ok)
        throw new Error(`Documentation export failed (${response.status})`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "openapi.json";
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage("OpenAPI document exported.");
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Documentation export failed.",
      );
    }
  }

  async function importOpenAPI(file: File) {
    if (!token || !workspaceId) return;
    try {
      const text = await file.text();
      const spec = JSON.parse(text);
      const result = await api<{
        collection_name: string;
        folder_count: number;
        request_count: number;
      }>(
        `/workspaces/${workspaceId}/documentation/import`,
        { method: "POST", body: JSON.stringify({ spec }) },
        token,
      );
      await loadCollections(workspaceId, token);
      await loadDocumentationSummary();
      setMessage(
        `Imported ${result.request_count} requests into ${result.collection_name}.`,
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "OpenAPI import failed.");
    }
  }

  async function logout() {
    if (token)
      await api("/auth/logout", { method: "POST" }, token).catch(() => {});
    setToken(null);
    setUser(null);
    setWorkspaces([]);
    setCollections([]);
    setSelectedRequest(null);
  }

  const treeFolders = useMemo(
    () => folders.filter((f) => f.parent_id === null),
    [folders],
  );

  if (!user || !token)
    return (
      <main className="shell">
        <section className="hero auth-card">
          <span className="eyebrow">APIForge · Phase 8</span>
          <h1>Your API workspace starts here.</h1>
          <p>
            Collections, folders, persisted request definitions, and workspace
            environments are available. Requests can now be searched, filtered,
            paginated, sorted, and executed through the security-validated
            execution engine.
          </p>
          <form onSubmit={submit} className="auth-form">
            {mode === "register" && (
              <label>
                Name
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
            )}
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />
            </label>
            <button disabled={loading}>
              {loading
                ? "Working…"
                : mode === "login"
                  ? "Log in"
                  : "Create account"}
            </button>
          </form>
          <button
            className="link-button"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
          >
            {mode === "login"
              ? "Need an account? Register"
              : "Already have an account? Log in"}
          </button>
          {message && <div className="message">{message}</div>}
        </section>
      </main>
    );

  return (
    <main className="app-shell">
      <header className="topbar">
        <strong>APIForge</strong>
        <div className="global-search">
          <input
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              if (!e.target.value.trim()) setSearchResults([]);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") runSearch();
            }}
            placeholder="Search collections, folders, requests…"
          />
          <button type="button" onClick={() => runSearch()}>
            Search
          </button>
          {searchResults.length > 0 && (
            <div className="search-results">
              {searchResults.map((item) => (
                <button
                  type="button"
                  key={`${item.resource_type}-${item.id}`}
                  onClick={() => selectSearchResult(item)}
                >
                  <span>
                    {item.resource_type}
                    {item.method ? ` · ${item.method}` : ""}
                  </span>
                  <strong>{item.name}</strong>
                  {item.url && <small>{item.url}</small>}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="workspace-select">
          <select
            value={workspaceId}
            onChange={async (e) => {
              setWorkspaceId(e.target.value);
              await Promise.all([
                loadCollections(e.target.value),
                loadEnvironments(e.target.value),
              ]);
            }}
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
          <select
            value={environmentId}
            onChange={async (e) => {
              setEnvironmentId(e.target.value);
              await loadVariables(e.target.value);
            }}
          >
            <option value="">Environment</option>
            {environments.map((env) => (
              <option key={env.id} value={env.id}>
                {env.name}
              </option>
            ))}
          </select>
          <button onClick={createEnvironment}>+ Env</button>
          <button
            onClick={async () => {
              setDocumentationOpen(true);
              await loadDocumentationSummary();
            }}
          >
            Docs
          </button>
          <button
            onClick={async () => {
              setAuditOpen(true);
              await loadAuditLogs();
            }}
          >
            Audit
          </button>
          <button onClick={logout}>Log out</button>
        </div>
      </header>
      {auditOpen && (
        <section className="documentation-panel">
          <div className="section-head">
            <span>Security Audit Log</span>
            <button onClick={() => setAuditOpen(false)}>Close</button>
          </div>
          {auditLogs.length === 0 ? (
            <p className="muted">No audit entries are available or you do not have audit-log permission.</p>
          ) : (
            <div className="audit-list">
              {auditLogs.map((log) => (
                <div className="audit-row" key={log.id}>
                  <strong>{log.action}</strong>
                  <span className={`status-badge status-${Math.floor(log.status_code / 100)}xx`}>{log.status_code}</span>
                  <code>{log.path}</code>
                  <small>{new Date(log.created_at).toLocaleString()}</small>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
      {documentationOpen && (
        <section className="documentation-panel">
          <div className="section-head">
            <span>API Documentation</span>
            <button onClick={() => setDocumentationOpen(false)}>Close</button>
          </div>
          {documentationSummary && (
            <p>
              {documentationSummary.title} · OpenAPI {documentationSummary.version} · {documentationSummary.collection_count} collections · {documentationSummary.request_count} requests
            </p>
          )}
          <div className="documentation-actions">
            <button onClick={exportOpenAPI}>Export OpenAPI JSON</button>
            <label className="file-button">
              Import OpenAPI JSON
              <input
                type="file"
                accept="application/json,.json"
                hidden
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void importOpenAPI(file);
                  e.currentTarget.value = "";
                }}
              />
            </label>
          </div>
          <small>Credentials are never exported. Imported authentication schemes require credentials to be configured separately.</small>
        </section>
      )}
      <div className="workspace-grid">
        <aside className="sidebar">
          <div className="section-head">
            <span>Collections</span>
            <button onClick={createCollection}>+</button>
          </div>
          {collections.length === 0 ? (
            <div className="empty">
              Your workspace is empty.
              <br />
              <button onClick={createCollection}>Create collection</button>
            </div>
          ) : (
            collections.map((c) => (
              <div
                key={c.id}
                className={`collection ${selectedCollection?.id === c.id ? "active" : ""}`}
                onClick={async () => {
                  setSelectedCollection(c);
                  await loadChildren(c.id);
                }}
              >
                <div className="collection-title">
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedCollection(c);
                    }}
                  >
                    {selectedCollection?.id === c.id ? "▾" : "▸"} {c.name}
                  </span>
                  {selectedCollection?.id === c.id && (
                    <button
                      className="icon-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteCollection();
                      }}
                    >
                      ×
                    </button>
                  )}
                </div>
                {selectedCollection?.id === c.id && (
                  <>
                    <div className="tree-label row-label">
                      <span>Folders</span>
                      <button
                        className="mini-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          createFolder();
                        }}
                      >
                        +
                      </button>
                    </div>
                    {treeFolders.map((f) => (
                      <div className="tree-item" key={f.id}>
                        ▰ {f.name}
                      </div>
                    ))}
                    {folders.length === 0 && (
                      <div className="muted">No folders</div>
                    )}
                    <div className="tree-label row-label">
                      <span>Environment Variables</span>
                      <button
                        className="mini-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          createVariable();
                        }}
                      >
                        +
                      </button>
                    </div>
                    {environmentId &&
                      variables.map((v) => (
                        <div className="tree-item" key={v.id}>
                          ◆ {v.key}
                          {v.is_secret ? " · secret" : ""}
                        </div>
                      ))}
                    {environmentId && variables.length === 0 && (
                      <div className="muted">No variables</div>
                    )}
                    <div className="tree-label row-label">
                      <span>Requests</span>
                      <button
                        className="mini-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          createRequest();
                        }}
                      >
                        +
                      </button>
                    </div>
                    {requests.map((r) => (
                      <button
                        className={`request-item ${selectedRequest?.id === r.id ? "selected" : ""}`}
                        key={r.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedRequest(r);
                        }}
                      >
                        <span>{r.method}</span>
                        {r.name}
                      </button>
                    ))}
                    <button
                      className="add-request"
                      onClick={(e) => {
                        e.stopPropagation();
                        createRequest();
                      }}
                    >
                      + Request
                    </button>
                  </>
                )}
              </div>
            ))
          )}
        </aside>
        <section className="editor">
          {selectedRequest ? (
            <form onSubmit={saveRequest}>
              <div className="editor-toolbar">
                <div className="request-line">
                  <select
                    value={method}
                    onChange={(e) => setMethod(e.target.value)}
                  >
                    {[
                      "GET",
                      "POST",
                      "PUT",
                      "PATCH",
                      "DELETE",
                      "HEAD",
                      "OPTIONS",
                    ].map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                  </select>
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://api.example.com/users"
                  />
                  <button type="submit">Save</button>
                  <button type="button" onClick={deleteRequest}>
                    Delete
                  </button>
                  <button
                    type="button"
                    onClick={executeSelectedRequest}
                    disabled={executing || !environmentId}
                  >
                    {executing ? "Sending…" : "Send"}
                  </button>
                </div>
                <input
                  className="request-name"
                  value={requestName}
                  onChange={(e) => setRequestName(e.target.value)}
                  placeholder="Request name"
                />
                {Object.values(presence).length > 0 && (
                  <div className="presence-bar">
                    <span className="presence-dot" />
                    {Object.values(presence).map((item) => (
                      <span key={item.connection_id} className="presence-user">
                        {item.name}
                        {item.user_id === user.id ? " (you)" : ""}
                      </span>
                    ))}
                    <small>
                      {collaborationReady ? "live" : "reconnecting"}
                    </small>
                  </div>
                )}
              </div>
              <nav className="tabs">
                {["params", "headers", "body", "auth"].map((tab) => (
                  <span
                    key={tab}
                    className={activeTab === tab ? "active" : ""}
                    onClick={() => setActiveTab(tab as any)}
                    style={{ cursor: "pointer" }}
                  >
                    {tab.charAt(0).toUpperCase() + tab.slice(1)}
                  </span>
                ))}
              </nav>
              <div className="editor-panel">
                {activeTab === "body" && (
                  <label>
                    Body
                    <textarea
                      value={body}
                      onChange={(e) => setBody(e.target.value)}
                      placeholder='{"key":"value"}'
                    />
                  </label>
                )}
                {activeTab === "params" && (
                  <div className="muted">
                    Params editing is not implemented in this phase.
                  </div>
                )}
                {activeTab === "headers" && (
                  <div className="muted">
                    Headers editing is not implemented in this phase.
                  </div>
                )}
                {activeTab === "auth" && (
                  <div
                    className="auth-editor"
                    style={{ display: "grid", gap: "12px", marginTop: "12px" }}
                  >
                    <h3>Authentication Configuration</h3>
                    <label style={{ display: "grid", gap: "6px" }}>
                      Type
                      <select
                        value={authType}
                        onChange={(e) => setAuthType(e.target.value)}
                      >
                        <option value="none">None</option>
                        <option value="bearer">Bearer Token</option>
                        <option value="basic">Basic Auth</option>
                      </select>
                    </label>
                    {authType === "bearer" && (
                      <label style={{ display: "grid", gap: "6px" }}>
                        Token (Write-Only)
                        <input
                          type="password"
                          value={authToken}
                          onChange={(e) => setAuthToken(e.target.value)}
                          placeholder={
                            selectedRequest?.auth_config?.has_token
                              ? "Saved Bearer Token Masked (enter to change)"
                              : "Enter token"
                          }
                        />
                      </label>
                    )}
                    {authType === "basic" && (
                      <>
                        <label style={{ display: "grid", gap: "6px" }}>
                          Username
                          <input
                            type="text"
                            value={authUsername}
                            onChange={(e) => setAuthUsername(e.target.value)}
                            placeholder="Username"
                          />
                        </label>
                        <label style={{ display: "grid", gap: "6px" }}>
                          Password (Write-Only)
                          <input
                            type="password"
                            value={authPassword}
                            onChange={(e) => setAuthPassword(e.target.value)}
                            placeholder={
                              selectedRequest?.auth_config?.has_credentials
                                ? "Saved Password Masked (enter to change)"
                                : "Enter password"
                            }
                          />
                        </label>
                      </>
                    )}
                    <button
                      type="button"
                      onClick={updateAuthConfig}
                      style={{ marginTop: "12px", width: "max-content" }}
                    >
                      Update Authentication Configuration
                    </button>
                  </div>
                )}
                <div className="notice">
                  Requests execute through the Phase 6 security-validated
                  execution engine. Select an environment before sending.
                </div>
                {execution && (
                  <section className="response-panel">
                    <div className="response-head">
                      <strong>
                        {execution.success
                          ? `${execution.status_code} ${execution.status_code >= 200 && execution.status_code < 300 ? "OK" : "HTTP Response"}`
                          : execution.error_code}
                      </strong>
                      <span>
                        {execution.duration_ms != null
                          ? `${execution.duration_ms} ms`
                          : ""}
                      </span>
                    </div>
                    {execution.success ? (
                      <>
                        <div className="response-tabs">
                          <span>Body</span>
                          <span>Headers</span>
                          <span>Metadata</span>
                        </div>
                        <pre className="response-body">
                          {execution.body_is_text
                            ? execution.body || "(empty response)"
                            : `Binary response: ${execution.content_type || "unknown"} · ${execution.response_size_bytes} bytes`}
                        </pre>
                        <details>
                          <summary>Headers</summary>
                          <pre className="response-body">
                            {JSON.stringify(execution.headers, null, 2)}
                          </pre>
                        </details>
                      </>
                    ) : (
                      <div className="execution-error">
                        {execution.error_message}
                      </div>
                    )}
                  </section>
                )}
              </div>
            </form>
          ) : (
            <div className="empty-editor">
              <h2>Select a request</h2>
              <p>Create a request in a collection to start editing it.</p>
            </div>
          )}
          {message && <div className="toast">{message}</div>}
        </section>
      </div>
    </main>
  );
}
