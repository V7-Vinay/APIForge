export type User = {
  id: string;
  name: string;
  email: string;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type WorkspaceRole = "OWNER" | "ADMIN" | "EDITOR" | "VIEWER";

export type Workspace = {
  id: string;
  name: string;
  slug: string;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type WorkspaceMember = {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: WorkspaceRole;
  created_at: string;
};

export type Invitation = {
  id: string;
  workspace_id: string;
  email: string;
  role: WorkspaceRole;
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
};

export type Collection = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  position: number;
  created_at: string;
  updated_at: string;
};

export type Folder = {
  id: string;
  collection_id: string;
  parent_id: string | null;
  name: string;
  position: number;
  created_at: string;
  updated_at: string;
};

export type HttpMethod =
  | "GET"
  | "POST"
  | "PUT"
  | "PATCH"
  | "DELETE"
  | "HEAD"
  | "OPTIONS";

export type KeyValue = {
  key: string;
  value: string;
  enabled: boolean;
};

export type RequestAuthType = "none" | "bearer" | "basic";

export type RequestAuth = {
  type: RequestAuthType;
  username?: string | null;
  has_credentials?: boolean | null;
  has_token?: boolean | null;
};

export type AuthConfigWrite = {
  type: RequestAuthType;
  token?: string;
  username?: string;
  password?: string;
};

export type ApiRequest = {
  id: string;
  collection_id: string;
  folder_id: string | null;
  name: string;
  description: string | null;
  method: string;
  url: string;
  headers: KeyValue[] | null;
  query_params: KeyValue[] | null;
  body: string | null;
  auth_config: RequestAuth | null;
  position: number;
  created_at: string;
  updated_at: string;
};

export type Environment = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type Variable = {
  id: string;
  environment_id: string;
  key: string;
  is_secret: boolean;
  created_at: string;
  updated_at: string;
};

export type RevealedVariable = Variable & { value: string };

export type Execution = {
  success: boolean;
  status_code?: number | null;
  headers?: Record<string, string> | null;
  body?: string | null;
  content_type?: string | null;
  response_size_bytes?: number | null;
  body_is_text?: boolean | null;
  duration_ms?: number | null;
  redirects?: number | null;
  error_code?: string | null;
  error_message?: string | null;
};

export type HistoryItem = {
  id: string;
  request_id: string;
  environment_id: string | null;
  method: string;
  url: string;
  status_code: number | null;
  success: boolean;
  duration_ms: number | null;
  response_size_bytes: number;
  response_headers: Record<string, string>;
  response_body: string | null;
  content_type: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
};

export type SearchItem = {
  id: string;
  resource_type: "collection" | "folder" | "request";
  name: string;
  description: string | null;
  collection_id: string | null;
  folder_id: string | null;
  method: string | null;
  url: string | null;
  position: number;
  created_at: string;
  updated_at: string;
};

export type Paginated<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type DocumentationSummary = {
  title: string;
  version: string;
  collection_count: number;
  folder_count: number;
  request_count: number;
};

export type OpenAPIImportResult = {
  collection_id: string;
  collection_name: string;
  folder_count: number;
  request_count: number;
};

export type AuditLog = {
  id: string;
  user_id: string | null;
  workspace_id: string | null;
  action: string;
  method: string;
  path: string;
  status_code: number;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type HealthResponse = {
  status: string;
  service?: string;
  version?: string;
};

export type ReadyResponse = {
  status: string;
  postgres: string;
  redis: string;
};

export type AppInfo = {
  name: string;
  version: string;
  build_sha?: string;
  status: string;
};

export type CollaborationPresence = {
  connection_id: string;
  user_id: string;
  name: string;
  request_id: string;
  last_seen: string;
};

export type CollaborationEvent = {
  id?: string;
  type: string;
  workspace_id?: string;
  actor_id?: string | null;
  request_id?: string | null;
  resource_id?: string | null;
  resource_type?: string | null;
  timestamp?: string;
  payload?: Record<string, unknown>;
};

export type ConnectionState = "CONNECTED" | "RECONNECTING" | "DISCONNECTED";

export const HTTP_METHODS: HttpMethod[] = [
  "GET",
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
  "HEAD",
  "OPTIONS",
];

export const WORKSPACE_ROLES: WorkspaceRole[] = [
  "OWNER",
  "ADMIN",
  "EDITOR",
  "VIEWER",
];

export const INVITABLE_ROLES: WorkspaceRole[] = ["ADMIN", "EDITOR", "VIEWER"];
