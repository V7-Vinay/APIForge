import { useMemo, useState, type ReactNode } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useNavigate,
  useParams,
} from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useToast } from "../contexts/ToastContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { Button } from "../components/ui/Button";
import { Select } from "../components/ui/Input";
import { Badge, Spinner } from "../components/ui/Tabs";
import { canViewAudit } from "../utils/permissions";
import type { ConnectionState } from "../types/api";

export type AppShellOutletContext = {
  connectionState: ConnectionState;
  setConnectionState: (state: ConnectionState) => void;
};

type Props = {
  onOpenSearch?: () => void;
  children?: ReactNode;
};

export function AppShell({ onOpenSearch, children }: Props) {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const toast = useToast();
  const { workspace, workspaces, role, loading } = useWorkspace();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("DISCONNECTED");

  const base = workspaceId ? `/workspaces/${workspaceId}` : "/workspaces";

  const navItems = useMemo(() => {
    const items = [
      { to: `${base}/overview`, label: "Overview", end: true },
      { to: `${base}/collections`, label: "Collections" },
      { to: `${base}/environments`, label: "Environments" },
      { to: `${base}/documentation`, label: "Documentation" },
      { to: `${base}/members`, label: "Members" },
      ...(canViewAudit(role)
        ? [{ to: `${base}/audit`, label: "Audit" }]
        : []),
      { to: `${base}/settings`, label: "Settings" },
      { to: `${base}/system`, label: "System" },
    ];
    return items;
  }, [base, role]);

  const outletContext: AppShellOutletContext = {
    connectionState,
    setConnectionState,
  };

  async function handleLogout() {
    try {
      await logout();
      toast.success("Signed out.");
      navigate("/login", { replace: true });
    } catch {
      toast.error("Could not sign out cleanly.");
      navigate("/login", { replace: true });
    }
  }

  function handleWorkspaceChange(nextId: string) {
    if (!nextId || nextId === workspaceId) return;
    navigate(`/workspaces/${nextId}/overview`);
  }

  function handleOpenSearch() {
    if (onOpenSearch) {
      onOpenSearch();
      return;
    }
    if (workspaceId) {
      navigate(`${base}/collections`, { state: { openSearch: true } });
    }
  }

  const connectionTone =
    connectionState === "CONNECTED"
      ? "success"
      : connectionState === "RECONNECTING"
        ? "warning"
        : "neutral";

  return (
    <div
      className={`app-shell ${sidebarCollapsed ? "sidebar-collapsed" : ""}`.trim()}
    >
      <header className="topbar">
        <div className="topbar-left">
          <Button
            variant="ghost"
            size="sm"
            className="sidebar-toggle"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-pressed={sidebarCollapsed}
            onClick={() => setSidebarCollapsed((v) => !v)}
          >
            ☰
          </Button>
          <Link to="/workspaces" className="topbar-brand">
            APIForge
          </Link>
          <div className="workspace-select">
            <Select
              aria-label="Workspace"
              value={workspaceId ?? ""}
              onChange={(e) => handleWorkspaceChange(e.target.value)}
              disabled={loading && !workspaces.length}
            >
              {workspaces.length === 0 ? (
                <option value="">No workspaces</option>
              ) : (
                workspaces.map((ws) => (
                  <option key={ws.id} value={ws.id}>
                    {ws.name}
                  </option>
                ))
              )}
            </Select>
          </div>
        </div>

        <div className="topbar-right">
          <Button
            variant="subtle"
            size="sm"
            className="global-search-trigger"
            onClick={handleOpenSearch}
            disabled={!workspaceId}
            aria-label="Search collections, folders, requests"
          >
            <span className="search-trigger-label">
              Search collections, folders, requests…
            </span>
            <kbd className="kbd">⌘K</kbd>
          </Button>

          <div className="user-menu">
            <Button
              variant="ghost"
              size="sm"
              className="user-menu-trigger"
              aria-expanded={userMenuOpen}
              aria-haspopup="menu"
              onClick={() => setUserMenuOpen((v) => !v)}
            >
              {user?.name ?? "Account"}
            </Button>
            {userMenuOpen ? (
              <div className="user-menu-dropdown" role="menu">
                <div className="user-menu-meta">
                  <strong>{user?.name}</strong>
                  <span>{user?.email}</span>
                </div>
                <Link
                  to={`${base}/account`}
                  className="user-menu-item"
                  role="menuitem"
                  onClick={() => setUserMenuOpen(false)}
                >
                  Account
                </Link>
                <Link
                  to={`${base}/settings`}
                  className="user-menu-item"
                  role="menuitem"
                  onClick={() => setUserMenuOpen(false)}
                >
                  Workspace settings
                </Link>
                <button
                  type="button"
                  className="user-menu-item"
                  role="menuitem"
                  onClick={() => {
                    setUserMenuOpen(false);
                    void handleLogout();
                  }}
                >
                  Log out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      <div className="app-body">
        <aside className="sidebar" aria-label="Workspace navigation">
          <div className="sidebar-workspace">
            {loading && !workspace ? (
              <Spinner label="Loading workspace" />
            ) : (
              <>
                <strong>{workspace?.name ?? "Workspace"}</strong>
                {role ? <Badge tone="info">{role}</Badge> : null}
              </>
            )}
          </div>
          <nav className="sidebar-nav">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={"end" in item ? item.end : false}
                className={({ isActive }) =>
                  `nav-item ${isActive ? "active" : ""}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="content">
          {children ?? <Outlet context={outletContext} />}
        </main>
      </div>

      <footer className="status-bar">
        <span className="status-bar-item">
          Connection{" "}
          <Badge tone={connectionTone}>{connectionState}</Badge>
        </span>
        <span className="status-bar-item">
          {workspace ? `${workspace.name} · ${workspace.slug}` : "No workspace"}
        </span>
      </footer>
    </div>
  );
}
