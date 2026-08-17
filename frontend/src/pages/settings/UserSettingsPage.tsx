import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { workspacesApi } from "../../api/workspaces";
import { ApiError } from "../../api/client";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { Button } from "../../components/ui/Button";
import { Panel, Spinner } from "../../components/ui/Tabs";
import { formatDateTime } from "../../utils/format";
import type { Workspace } from "../../types/api";

export function UserSettingsPage() {
  const { user, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(true);
  const [loggingOut, setLoggingOut] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoadingWorkspaces(true);
      try {
        const list = await workspacesApi.list();
        if (!cancelled) setWorkspaces(list);
      } catch (err) {
        if (!cancelled) {
          toast.error(
            err instanceof ApiError
              ? err.message
              : "Could not load workspace context.",
          );
        }
      } finally {
        if (!cancelled) setLoadingWorkspaces(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [toast]);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
      toast.success("Signed out.");
      navigate("/login", { replace: true });
    } catch {
      toast.error("Signed out locally.");
      navigate("/login", { replace: true });
    } finally {
      setLoggingOut(false);
    }
  }

  function handleThemeChange(newTheme: string) {
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);
    document.documentElement.setAttribute("data-theme", newTheme);
    toast.success(`Switched to ${newTheme} theme.`);
  }

  if (!user) {
    return (
      <div className="page">
        <h1>Settings</h1>
        <p>You are not signed in.</p>
        <Link to="/login">Sign in</Link>
      </div>
    );
  }

  return (
    <div className="page user-settings-page">
      <header className="page-header">
        <div>
          <h1>Account settings</h1>
          <p>
            Your profile and session. Profile editing is not available via the
            API.
          </p>
        </div>
      </header>

      <Panel title="Profile">
        <dl className="detail-list">
          <div>
            <dt>Name</dt>
            <dd>{user.name}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>User ID</dt>
            <dd>
              <code>{user.id}</code>
            </dd>
          </div>
          <div>
            <dt>Member since</dt>
            <dd>{formatDateTime(user.created_at)}</dd>
          </div>
        </dl>
      </Panel>

      <Panel title="Workspace context">
        {loadingWorkspaces ? (
          <Spinner label="Loading workspaces" />
        ) : workspaces.length === 0 ? (
          <p className="muted">
            You are not a member of any workspace.{" "}
            <Link to="/workspaces">Create one</Link>
          </p>
        ) : (
          <ul className="workspace-context-list">
            {workspaces.map((ws) => (
              <li key={ws.id}>
                <Link to={`/workspaces/${ws.id}/overview`}>
                  <strong>{ws.name}</strong>
                  <span className="muted"> · {ws.slug}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Preferences">
        <div className="stack-form">
          <div className="field">
            <span className="field-label">Theme</span>
            <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
              <Button
                variant={theme === "dark" ? "primary" : "secondary"}
                onClick={() => handleThemeChange("dark")}
                size="sm"
              >
                Dark Mode
              </Button>
              <Button
                variant={theme === "light" ? "primary" : "secondary"}
                onClick={() => handleThemeChange("light")}
                size="sm"
              >
                Light Mode
              </Button>
            </div>
          </div>
        </div>
      </Panel>

      <Panel title="Session">
        <Button
          variant="danger"
          loading={loggingOut}
          onClick={() => void handleLogout()}
        >
          Log out
        </Button>
      </Panel>
    </div>
  );
}
