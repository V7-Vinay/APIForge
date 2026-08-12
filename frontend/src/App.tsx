import { FormEvent, useEffect, useMemo, useState } from "react";

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
  } | null;
  position: number;
};

async function api<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
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
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      body?.detail ??
        body?.error?.message ??
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
  const [loading, setLoading] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [collections, setCollections] = useState<Collection[]>([]);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [requests, setRequests] = useState<APIRequest[]>([]);
  const [selectedCollection, setSelectedCollection] =
    useState<Collection | null>(null);
  const [selectedRequest, setSelectedRequest] = useState<APIRequest | null>(
    null,
  );
  const [requestName, setRequestName] = useState("");
  const [method, setMethod] = useState("GET");
  const [url, setUrl] = useState("");
  const [body, setBody] = useState("");

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
      await loadCollections(data[0].id, accessToken);
    }
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
    if (selectedRequest) {
      setRequestName(selectedRequest.name);
      setMethod(selectedRequest.method);
      setUrl(selectedRequest.url);
      setBody(selectedRequest.body ?? "");
    }
  }, [selectedRequest]);

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
          <span className="eyebrow">APIForge · Phase 4</span>
          <h1>Your API workspace starts here.</h1>
          <p>
            Collections, folders and persisted request definitions are now
            available. Requests are stored only; execution arrives in Phase 6.
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
        <div className="workspace-select">
          <select
            value={workspaceId}
            onChange={async (e) => {
              setWorkspaceId(e.target.value);
              await loadCollections(e.target.value);
            }}
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
          <button onClick={logout}>Log out</button>
        </div>
      </header>
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
                    disabled
                    title="Request execution is Phase 6"
                  >
                    Send
                  </button>
                </div>
                <input
                  className="request-name"
                  value={requestName}
                  onChange={(e) => setRequestName(e.target.value)}
                  placeholder="Request name"
                />
              </div>
              <nav className="tabs">
                <span className="active">Params</span>
                <span>Headers</span>
                <span>Body</span>
                <span>Auth</span>
              </nav>
              <div className="editor-panel">
                <div className="muted">Request definition editor</div>
                <label>
                  Body
                  <textarea
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    placeholder='{"key":"value"}'
                  />
                </label>
                <div className="notice">
                  Execution is intentionally disabled in Phase 4. The saved
                  definition will be executed by the Phase 6 execution engine.
                </div>
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
