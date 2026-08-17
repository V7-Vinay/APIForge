import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import {
  inviteWithDebugToken,
  workspacesApi,
} from "../../api/workspaces";
import { ApiError } from "../../api/client";
import { useAuth } from "../../contexts/AuthContext";
import { useToast } from "../../contexts/ToastContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import { Button } from "../../components/ui/Button";
import { Field, Input, Select } from "../../components/ui/Input";
import { ConfirmDialog, Modal } from "../../components/ui/Modal";
import {
  Badge,
  EmptyState,
  Panel,
  Spinner,
} from "../../components/ui/Tabs";
import { formatDateTime } from "../../utils/format";
import { canManageMembers } from "../../utils/permissions";
import {
  INVITABLE_ROLES,
  type WorkspaceMember,
  type WorkspaceRole,
} from "../../types/api";

export function MembersPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { user } = useAuth();
  const toast = useToast();
  const { members, role, loading, refreshMembers } = useWorkspace();

  const manage = canManageMembers(role);

  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<WorkspaceRole>("EDITOR");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [debugToken, setDebugToken] = useState<string | null>(null);
  const [debugLink, setDebugLink] = useState<string | null>(null);

  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [removeTarget, setRemoveTarget] = useState<WorkspaceMember | null>(
    null,
  );
  const [removing, setRemoving] = useState(false);

  function openInvite() {
    setInviteEmail("");
    setInviteRole("EDITOR");
    setInviteError(null);
    setDebugToken(null);
    setDebugLink(null);
    setInviteOpen(true);
  }

  async function handleInvite(event: FormEvent) {
    event.preventDefault();
    if (!workspaceId || !manage) return;
    const email = inviteEmail.trim();
    if (!email) {
      setInviteError("Email is required.");
      return;
    }
    setInviting(true);
    setInviteError(null);
    setDebugToken(null);
    setDebugLink(null);
    try {
      const { debugToken: token } = await inviteWithDebugToken(
        workspaceId,
        email,
        inviteRole,
      );
      toast.success(`Invitation sent to ${email}.`);
      if (token) {
        setDebugToken(token);
        setDebugLink(`${window.location.origin}/invitations/${token}/accept`);
      } else {
        setInviteOpen(false);
      }
      setInviteEmail("");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Could not send invitation.";
      setInviteError(message);
      toast.error(message);
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(member: WorkspaceMember, next: WorkspaceRole) {
    if (!workspaceId || !manage || member.role === next) return;
    if (member.role === "OWNER") {
      toast.warning("Owner role cannot be changed here.");
      return;
    }
    setBusyUserId(member.user_id);
    try {
      await workspacesApi.updateMemberRole(workspaceId, member.user_id, next);
      await refreshMembers();
      toast.success(`Updated role for ${member.name}.`);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Could not update role.",
      );
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleRemove() {
    if (!workspaceId || !removeTarget || !manage) return;
    setRemoving(true);
    try {
      await workspacesApi.removeMember(workspaceId, removeTarget.user_id);
      await refreshMembers();
      toast.success(`${removeTarget.name} was removed.`);
      setRemoveTarget(null);
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Could not remove member.",
      );
    } finally {
      setRemoving(false);
    }
  }

  if (loading && members.length === 0) {
    return (
      <div className="page-loading">
        <Spinner label="Loading members" />
      </div>
    );
  }

  return (
    <div className="page members-page">
      <header className="page-header">
        <div>
          <h1>Members</h1>
          <p>People with access to this workspace.</p>
        </div>
        {manage ? (
          <Button variant="primary" onClick={openInvite}>
            Invite member
          </Button>
        ) : null}
      </header>

      {members.length === 0 ? (
        <EmptyState
          title="No members"
          description="Invite teammates to collaborate in this workspace."
          action={
            manage ? (
              <Button variant="primary" onClick={openInvite}>
                Invite member
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Panel>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Joined</th>
                  {manage ? <th>Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {members.map((member) => {
                  const isSelf = user?.id === member.user_id;
                  const isOwner = member.role === "OWNER";
                  const canEditRow = manage && !isOwner;
                  return (
                    <tr key={member.id}>
                      <td>
                        {member.name}
                        {isSelf ? (
                          <Badge tone="neutral">You</Badge>
                        ) : null}
                      </td>
                      <td>{member.email}</td>
                      <td>
                        {canEditRow ? (
                          <Select
                            aria-label={`Role for ${member.name}`}
                            value={member.role}
                            disabled={busyUserId === member.user_id}
                            onChange={(e) =>
                              void handleRoleChange(
                                member,
                                e.target.value as WorkspaceRole,
                              )
                            }
                          >
                            {INVITABLE_ROLES.map((r) => (
                              <option key={r} value={r}>
                                {r}
                              </option>
                            ))}
                          </Select>
                        ) : (
                          <Badge tone={isOwner ? "info" : "neutral"}>
                            {member.role}
                          </Badge>
                        )}
                      </td>
                      <td>{formatDateTime(member.created_at)}</td>
                      {manage ? (
                        <td>
                          {canEditRow && !isSelf ? (
                            <Button
                              variant="danger"
                              size="sm"
                              disabled={busyUserId === member.user_id}
                              onClick={() => setRemoveTarget(member)}
                            >
                              Remove
                            </Button>
                          ) : (
                            <span className="muted">—</span>
                          )}
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <Modal
        open={inviteOpen}
        title="Invite member"
        onClose={() => !inviting && setInviteOpen(false)}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setInviteOpen(false)}
              disabled={inviting}
            >
              {debugToken ? "Close" : "Cancel"}
            </Button>
            {!debugToken ? (
              <Button
                type="submit"
                form="invite-member-form"
                variant="primary"
                loading={inviting}
              >
                Send invite
              </Button>
            ) : null}
          </>
        }
      >
        <form
          id="invite-member-form"
          className="stack-form"
          onSubmit={handleInvite}
        >
          <Field label="Email" htmlFor="invite-email">
            <Input
              id="invite-email"
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              disabled={inviting || !!debugToken}
              autoFocus
            />
          </Field>
          <Field label="Role" htmlFor="invite-role">
            <Select
              id="invite-role"
              value={inviteRole}
              onChange={(e) =>
                setInviteRole(e.target.value as WorkspaceRole)
              }
              disabled={inviting || !!debugToken}
            >
              {INVITABLE_ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
          </Field>
          {inviteError ? (
            <p className="form-error" role="alert">
              {inviteError}
            </p>
          ) : null}
          {debugToken ? (
            <div className="debug-invite" role="status">
              <p>
                <strong>Dev debug token</strong> (only returned in development):
              </p>
              <code className="debug-token">{debugToken}</code>
              {debugLink ? (
                <p>
                  Accept link:{" "}
                  <a href={debugLink} target="_blank" rel="noreferrer">
                    {debugLink}
                  </a>
                </p>
              ) : null}
            </div>
          ) : null}
        </form>
      </Modal>

      <ConfirmDialog
        open={!!removeTarget}
        title="Remove member?"
        message={
          removeTarget
            ? `Remove ${removeTarget.name} (${removeTarget.email}) from this workspace?`
            : ""
        }
        confirmLabel="Remove"
        danger
        loading={removing}
        onConfirm={() => void handleRemove()}
        onClose={() => !removing && setRemoveTarget(null)}
      />
    </div>
  );
}
