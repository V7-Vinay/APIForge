import { api, toQuery } from "./client";
import type {
  ApiRequest,
  AuthConfigWrite,
  Collection,
  Folder,
  KeyValue,
  Paginated,
} from "../types/api";

export type RequestWrite = {
  name: string;
  description?: string | null;
  method: string;
  url: string;
  headers?: KeyValue[];
  query_params?: KeyValue[];
  body?: string | null;
  auth_config?: AuthConfigWrite;
  folder_id?: string | null;
};

export type RequestPatch = Partial<RequestWrite>;

export const collectionsApi = {
  list(workspaceId: string) {
    return api<Collection[]>(`/workspaces/${workspaceId}/collections`);
  },
  page(
    workspaceId: string,
    params: {
      q?: string;
      page?: number;
      page_size?: number;
      sort_by?: string;
      sort_order?: string;
    } = {},
  ) {
    return api<Paginated<Collection>>(
      `/workspaces/${workspaceId}/collections/page${toQuery(params)}`,
    );
  },
  get(id: string) {
    return api<Collection>(`/collections/${id}`);
  },
  create(workspaceId: string, name: string, description?: string) {
    return api<Collection>(`/workspaces/${workspaceId}/collections`, {
      method: "POST",
      body: JSON.stringify({ name, description: description || null }),
    });
  },
  update(id: string, data: { name?: string; description?: string | null }) {
    return api<Collection>(`/collections/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  remove(id: string) {
    return api<void>(`/collections/${id}`, { method: "DELETE" });
  },
  reorder(id: string, position: number) {
    return api<Collection>(`/collections/${id}/reorder`, {
      method: "PATCH",
      body: JSON.stringify({ position }),
    });
  },
};

export const foldersApi = {
  list(collectionId: string) {
    return api<Folder[]>(`/collections/${collectionId}/folders`);
  },
  get(id: string) {
    return api<Folder>(`/folders/${id}`);
  },
  create(collectionId: string, name: string, parentId?: string | null) {
    return api<Folder>(`/collections/${collectionId}/folders`, {
      method: "POST",
      body: JSON.stringify({
        name,
        parent_id: parentId ?? null,
      }),
    });
  },
  update(
    id: string,
    data: { name?: string; parent_id?: string | null },
  ) {
    return api<Folder>(`/folders/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  remove(id: string) {
    return api<void>(`/folders/${id}`, { method: "DELETE" });
  },
  reorder(id: string, position: number) {
    return api<Folder>(`/folders/${id}/reorder`, {
      method: "PATCH",
      body: JSON.stringify({ position }),
    });
  },
};

export const requestsApi = {
  list(collectionId: string) {
    return api<ApiRequest[]>(`/collections/${collectionId}/requests`);
  },
  page(
    workspaceId: string,
    params: {
      q?: string;
      collection_id?: string;
      folder_id?: string;
      method?: string;
      page?: number;
      page_size?: number;
      sort_by?: string;
      sort_order?: string;
    } = {},
  ) {
    return api<Paginated<ApiRequest>>(
      `/workspaces/${workspaceId}/requests/page${toQuery(params)}`,
    );
  },
  get(id: string) {
    return api<ApiRequest>(`/requests/${id}`);
  },
  create(collectionId: string, data: RequestWrite) {
    return api<ApiRequest>(`/collections/${collectionId}/requests`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
  update(id: string, data: RequestPatch) {
    return api<ApiRequest>(`/requests/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
  remove(id: string) {
    return api<void>(`/requests/${id}`, { method: "DELETE" });
  },
  reorder(id: string, position: number) {
    return api<ApiRequest>(`/requests/${id}/reorder`, {
      method: "PATCH",
      body: JSON.stringify({ position }),
    });
  },
};
