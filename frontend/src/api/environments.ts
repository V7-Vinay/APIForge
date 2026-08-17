import { api } from "./client";
import type {
  Environment,
  RevealedVariable,
  Variable,
} from "../types/api";

export const environmentsApi = {
  list(workspaceId: string) {
    return api<Environment[]>(`/workspaces/${workspaceId}/environments`);
  },
  get(id: string) {
    return api<Environment>(`/environments/${id}`);
  },
  create(workspaceId: string, name: string, description?: string) {
    return api<Environment>(`/workspaces/${workspaceId}/environments`, {
      method: "POST",
      body: JSON.stringify({ name, description: description || null }),
    });
  },
  update(id: string, data: { name?: string; description?: string | null }) {
    return api<Environment>(`/environments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  remove(id: string) {
    return api<void>(`/environments/${id}`, { method: "DELETE" });
  },
  listVariables(environmentId: string) {
    return api<Variable[]>(`/environments/${environmentId}/variables`);
  },
  createVariable(
    environmentId: string,
    data: { key: string; value: string; is_secret?: boolean },
  ) {
    return api<Variable>(`/environments/${environmentId}/variables`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  getVariable(id: string) {
    return api<Variable>(`/environment-variables/${id}`);
  },
  revealVariable(id: string) {
    return api<RevealedVariable>(`/environment-variables/${id}/reveal`);
  },
  updateVariable(
    id: string,
    data: { key?: string; value?: string; is_secret?: boolean },
  ) {
    return api<Variable>(`/environment-variables/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  removeVariable(id: string) {
    return api<void>(`/environment-variables/${id}`, { method: "DELETE" });
  },
  resolve(environmentId: string, text: string) {
    return api<{ resolved_text: string }>(
      `/environments/${environmentId}/resolve`,
      {
        method: "POST",
        body: JSON.stringify({ text }),
      },
    );
  },
};
