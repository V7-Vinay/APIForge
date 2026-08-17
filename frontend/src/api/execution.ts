import { api, toQuery } from "./client";
import type {
  AuditLog,
  DocumentationSummary,
  Execution,
  HistoryItem,
  OpenAPIImportResult,
  Paginated,
  SearchItem,
  AppInfo,
  HealthResponse,
  ReadyResponse,
} from "../types/api";
import { download } from "./client";

export const executionApi = {
  execute(requestId: string, environmentId?: string | null) {
    return api<Execution>(`/requests/${requestId}/execute`, {
      method: "POST",
      body: JSON.stringify({
        environment_id: environmentId || null,
      }),
    });
  },
  history(requestId: string, limit = 50) {
    return api<HistoryItem[]>(
      `/requests/${requestId}/history${toQuery({ limit })}`,
    );
  },
};

export const searchApi = {
  search(
    workspaceId: string,
    params: {
      q?: string;
      resource_type?: string;
      collection_id?: string;
      folder_id?: string;
      method?: string;
      page?: number;
      page_size?: number;
      sort_by?: string;
      sort_order?: string;
    },
  ) {
    return api<Paginated<SearchItem>>(
      `/workspaces/${workspaceId}/search${toQuery(params)}`,
    );
  },
};

export const documentationApi = {
  summary(workspaceId: string) {
    return api<DocumentationSummary>(
      `/workspaces/${workspaceId}/documentation/summary`,
    );
  },
  exportOpenApi(workspaceId: string, filename = "openapi.json") {
    return download(
      `/workspaces/${workspaceId}/documentation/openapi.json`,
      filename,
    );
  },
  importOpenApi(
    workspaceId: string,
    spec: Record<string, unknown>,
    collectionName?: string,
  ) {
    return api<OpenAPIImportResult>(
      `/workspaces/${workspaceId}/documentation/import`,
      {
        method: "POST",
        body: JSON.stringify({
          spec,
          collection_name: collectionName || null,
        }),
      },
    );
  },
};

export const auditApi = {
  list(workspaceId: string, params: { limit?: number; before_id?: string } = {}) {
    return api<AuditLog[]>(
      `/workspaces/${workspaceId}/audit-logs${toQuery(params)}`,
    );
  },
};

export const systemApi = {
  health() {
    return api<HealthResponse>("/health");
  },
  ready() {
    return api<ReadyResponse>("/ready");
  },
  /** App identity from health — root `/` is the SPA, not the API. */
  async info(): Promise<AppInfo> {
    const health = await api<HealthResponse>("/health");
    return {
      name: health.service ?? "APIForge",
      version: health.version ?? "unknown",
      status: health.status,
    };
  },
};
