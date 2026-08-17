import { api, apiRaw, ApiError, toQuery } from "./client";
import type {
  Invitation,
  Workspace,
  WorkspaceMember,
  WorkspaceRole,
} from "../types/api";

export const workspacesApi = {
  list() {
    return api<Workspace[]>("/workspaces");
  },
  get(id: string) {
    return api<Workspace>(`/workspaces/${id}`);
  },
  create(name: string, slug: string) {
    return api<Workspace>("/workspaces", {
      method: "POST",
      body: JSON.stringify({ name, slug }),
    });
  },
  update(id: string, name: string) {
    return api<Workspace>(`/workspaces/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
  },
  remove(id: string) {
    return api<void>(`/workspaces/${id}`, { method: "DELETE" });
  },
  listMembers(workspaceId: string) {
    return api<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`);
  },
  updateMemberRole(workspaceId: string, userId: string, role: WorkspaceRole) {
    return api<WorkspaceMember>(
      `/workspaces/${workspaceId}/members/${userId}`,
      {
        method: "PATCH",
        body: JSON.stringify({ role }),
      },
    );
  },
  removeMember(workspaceId: string, userId: string) {
    return api<void>(`/workspaces/${workspaceId}/members/${userId}`, {
      method: "DELETE",
    });
  },
  invite(workspaceId: string, email: string, role: WorkspaceRole) {
    return api<Invitation>(`/workspaces/${workspaceId}/invitations`, {
      method: "POST",
      body: JSON.stringify({ email, role }),
    });
  },
  acceptInvitation(token: string) {
    return api<WorkspaceMember>(`/invitations/${token}/accept`, {
      method: "POST",
    });
  },
};

export async function inviteWithDebugToken(
  workspaceId: string,
  email: string,
  role: WorkspaceRole,
): Promise<{ invitation: Invitation; debugToken: string | null }> {
  const response = await apiRaw(`/workspaces/${workspaceId}/invitations`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      body?.error?.message ?? body?.detail ?? "Invitation failed.",
      response.status,
    );
  }
  return {
    invitation: body as Invitation,
    debugToken: response.headers.get("X-Debug-Invitation-Token"),
  };
}
