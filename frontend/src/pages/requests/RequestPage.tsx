import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { requestsApi } from "../../api/resources";
import { Button } from "../../components/ui/Button";
import { EmptyState, Spinner } from "../../components/ui/Tabs";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import RequestBuilder from "../../features/requests/RequestBuilder";
import type { ApiRequest } from "../../types/api";

export default function RequestPage() {
  const { workspaceId = "", requestId = "" } = useParams();
  const toast = useToast();
  const { upsertRequest } = useWorkspace();
  const [request, setRequest] = useState<ApiRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void requestsApi
      .get(requestId)
      .then((data) => {
        if (cancelled) return;
        setRequest(data);
        upsertRequest(data);
      })
      .catch((err) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError ? err.message : "Failed to load request.";
        setError(message);
        setRequest(null);
        toast.error(message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requestId, toast, upsertRequest]);

  if (loading) {
    return <Spinner label="Loading request" />;
  }

  if (error || !request) {
    return (
      <EmptyState
        title="Request not found"
        description={error ?? "This request may have been deleted or you lack access."}
        action={
          <Link to={`/workspaces/${workspaceId}/collections`}>
            <Button variant="secondary">Back to collections</Button>
          </Link>
        }
      />
    );
  }

  return (
    <div className="page request-page">
      <RequestBuilder
        request={request}
        onRequestChange={(next) => setRequest(next)}
      />
    </div>
  );
}
