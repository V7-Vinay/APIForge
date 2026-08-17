import type { WorkspaceRole } from "../types/api";

export type Permission =
  | "workspace:view"
  | "workspace:manage"
  | "workspace:members:manage"
  | "collections:manage"
  | "requests:edit"
  | "requests:execute"
  | "history:view"
  | "documentation:edit"
  | "environments:manage"
  | "audit:view";

const ROLE_PERMISSIONS: Record<WorkspaceRole, ReadonlySet<Permission>> = {
  OWNER: new Set([
    "workspace:view",
    "workspace:manage",
    "workspace:members:manage",
    "collections:manage",
    "requests:edit",
    "requests:execute",
    "history:view",
    "documentation:edit",
    "environments:manage",
    "audit:view",
  ]),
  ADMIN: new Set([
    "workspace:view",
    "workspace:manage",
    "workspace:members:manage",
    "collections:manage",
    "requests:edit",
    "requests:execute",
    "history:view",
    "documentation:edit",
    "environments:manage",
    "audit:view",
  ]),
  EDITOR: new Set([
    "workspace:view",
    "collections:manage",
    "requests:edit",
    "requests:execute",
    "history:view",
    "documentation:edit",
  ]),
  VIEWER: new Set(["workspace:view", "history:view"]),
};

export function hasPermission(
  role: WorkspaceRole | null | undefined,
  permission: Permission,
): boolean {
  if (!role) return false;
  return ROLE_PERMISSIONS[role].has(permission);
}

export function canDeleteWorkspace(role: WorkspaceRole | null | undefined): boolean {
  return role === "OWNER";
}

export function canManageMembers(role: WorkspaceRole | null | undefined): boolean {
  return hasPermission(role, "workspace:members:manage");
}

export function canManageCollections(role: WorkspaceRole | null | undefined): boolean {
  return hasPermission(role, "collections:manage");
}

export function canEditRequests(role: WorkspaceRole | null | undefined): boolean {
  return hasPermission(role, "requests:edit");
}

export function canExecuteRequests(role: WorkspaceRole | null | undefined): boolean {
  return hasPermission(role, "requests:execute");
}

export function canViewHistory(role: WorkspaceRole | null | undefined): boolean {
  return hasPermission(role, "history:view");
}

export function canManageEnvironments(role: WorkspaceRole | null | undefined): boolean {
  return hasPermission(role, "environments:manage");
}

export function canViewAudit(role: WorkspaceRole | null | undefined): boolean {
  return hasPermission(role, "audit:view");
}

export function canManageWorkspace(role: WorkspaceRole | null | undefined): boolean {
  return hasPermission(role, "workspace:manage");
}
