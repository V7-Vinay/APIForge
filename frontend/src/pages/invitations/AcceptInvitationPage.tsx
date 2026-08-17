import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { workspacesApi } from "../../api/workspaces";
import { ApiError } from "../../api/client";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Tabs";

export function AcceptInvitationPage() {
  const { token } = useParams<{ token: string }>();
  const { user, loading: authLoading } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const started = useRef(false);

  const [status, setStatus] = useState<"idle" | "working" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || started.current) return;
    if (!user) {
      navigate("/login", {
        replace: true,
        state: {
          from: { pathname: `/invitations/${token}/accept` },
          message: "Sign in with the invited email to accept this invitation.",
        },
      });
      return;
    }
    if (!token) {
      setStatus("error");
      setError("Invitation token is missing.");
      return;
    }

    started.current = true;
    setStatus("working");

    void (async () => {
      try {
        const before = await workspacesApi.list();
        await workspacesApi.acceptInvitation(token);
        const after = await workspacesApi.list();
        const joined =
          after.find((ws) => !before.some((b) => b.id === ws.id)) ??
          after.sort(
            (a, b) =>
              new Date(b.updated_at).getTime() -
              new Date(a.updated_at).getTime(),
          )[0];

        toast.success("Invitation accepted.");
        if (joined) {
          navigate(`/workspaces/${joined.id}/overview`, { replace: true });
        } else {
          navigate("/workspaces", { replace: true });
        }
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Could not accept invitation.";
        setError(message);
        setStatus("error");
        toast.error(message);
      }
    })();
  }, [authLoading, navigate, toast, token, user]);

  if (authLoading || status === "idle" || status === "working") {
    return (
      <div className="page-loading invitation-page">
        <Spinner label="Accepting invitation" />
        <p>Accepting your invitation…</p>
      </div>
    );
  }

  return (
    <div className="invitation-page invitation-error">
      <h1>Invitation could not be accepted</h1>
      <p className="form-error" role="alert">
        {error}
      </p>
      <div className="button-row">
        <Button variant="primary" onClick={() => navigate("/workspaces")}>
          Go to workspaces
        </Button>
        <Link to="/workspaces" className="text-link">
          Back
        </Link>
      </div>
    </div>
  );
}
