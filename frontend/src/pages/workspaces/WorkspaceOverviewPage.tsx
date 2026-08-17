import { Link, useParams } from "react-router-dom";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { Badge, Panel, Spinner } from "../../components/ui/Tabs";
import { formatDateTime } from "../../utils/format";
import {
  canManageMembers,
  canManageWorkspace,
} from "../../utils/permissions";

export function WorkspaceOverviewPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const {
    workspace,
    members,
    collections,
    environments,
    role,
    loading,
  } = useWorkspace();

  const base = `/workspaces/${workspaceId}`;

  if (loading && !workspace) {
    return (
      <div className="page-loading">
        <Spinner label="Loading overview" />
      </div>
    );
  }

  if (!workspace) {
    return (
      <div className="page">
        <h1>Workspace not found</h1>
        <p>This workspace may have been deleted or you no longer have access.</p>
        <div className="button-row">
          <Link to="/workspaces" className="btn btn-primary btn-md">
            Back to workspaces
          </Link>
        </div>
      </div>
    );
  }

  const creator = members.find((m) => m.user_id === workspace.created_by);

  return (
    <div className="page workspace-overview-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>{workspace.name}</h1>
          <p>
            <span className="muted">{workspace.slug}</span>
            {role ? (
              <>
                {" · "}
                <Badge tone="info">{role}</Badge>
              </>
            ) : null}
          </p>
        </div>
      </header>

      <div className="stat-row">
        <Panel title="Members">
          <p className="stat-value">{members.length}</p>
        </Panel>
        <Panel title="Collections">
          <p className="stat-value">{collections.length}</p>
        </Panel>
        <Panel title="Environments">
          <p className="stat-value">{environments.length}</p>
        </Panel>
      </div>

      <Panel title="Details" className="overview-details">
        <dl className="detail-list">
          <div>
            <dt>Created</dt>
            <dd>{formatDateTime(workspace.created_at)}</dd>
          </div>
          <div>
            <dt>Updated</dt>
            <dd>{formatDateTime(workspace.updated_at)}</dd>
          </div>
          <div>
            <dt>Creator</dt>
            <dd>
              {creator
                ? `${creator.name} (${creator.email})`
                : workspace.created_by}
            </dd>
          </div>
        </dl>
      </Panel>

      <Panel title="Quick actions">
        <div className="button-row">
          <Link to={`${base}/collections`} className="btn btn-primary btn-md">
            Open collections
          </Link>
          <Link
            to={`${base}/environments`}
            className="btn btn-secondary btn-md"
          >
            Environments
          </Link>
          {canManageMembers(role) ? (
            <Link to={`${base}/members`} className="btn btn-secondary btn-md">
              Invite members
            </Link>
          ) : (
            <Link to={`${base}/members`} className="btn btn-secondary btn-md">
              View members
            </Link>
          )}
          {canManageWorkspace(role) ? (
            <Link to={`${base}/settings`} className="btn btn-ghost btn-md">
              Workspace settings
            </Link>
          ) : null}
        </div>
      </Panel>
    </div>
  );
}
