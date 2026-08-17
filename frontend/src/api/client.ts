export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string | null,
    readonly details?: unknown,
    readonly retryAfter?: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type TokenProvider = () => string | null;
type UnauthorizedHandler = () => Promise<string | null>;

let getToken: TokenProvider = () => null;
let onUnauthorized: UnauthorizedHandler = async () => null;
let refreshing: Promise<string | null> | null = null;

export function configureApi(options: {
  getToken: TokenProvider;
  onUnauthorized: UnauthorizedHandler;
}) {
  getToken = options.getToken;
  onUnauthorized = options.onUnauthorized;
}

function messageFromBody(body: unknown, status: number): string {
  if (status === 429) {
    return "Too many requests. Please wait before trying again.";
  }
  if (!body || typeof body !== "object") {
    return `Request failed (${status}).`;
  }
  const record = body as Record<string, unknown>;
  const error = record.error as Record<string, unknown> | undefined;
  if (error?.message && typeof error.message === "string") return error.message;
  if (typeof record.detail === "string") return record.detail;
  if (Array.isArray(record.detail)) {
    return record.detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  return `Request failed (${status}).`;
}

async function parseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json().catch(() => null);
  }
  const text = await response.text().catch(() => "");
  return text || null;
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError("Network error. Check your connection and try again.", 0);
  }

  if (response.status === 401 && retry && !path.startsWith("/auth/")) {
    if (!refreshing) {
      refreshing = onUnauthorized().finally(() => {
        refreshing = null;
      });
    }
    const refreshed = await refreshing;
    if (refreshed) return api<T>(path, options, false);
  }

  if (response.status === 204) return undefined as T;

  const body = await parseBody(response);
  if (!response.ok) {
    const retryAfter = response.headers.get("Retry-After");
    let message = messageFromBody(body, response.status);
    if (response.status === 429 && retryAfter) {
      message = `Too many requests. Please try again in ${retryAfter} seconds.`;
    }
    const code =
      body && typeof body === "object" && "error" in body
        ? ((body as { error?: { code?: string } }).error?.code ?? null)
        : null;
    const details =
      body && typeof body === "object" && "error" in body
        ? (body as { error?: { details?: unknown } }).error?.details
        : undefined;
    throw new ApiError(message, response.status, code, details, retryAfter);
  }
  return body as T;
}

export async function apiRaw(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError("Network error. Check your connection and try again.", 0);
  }

  if (response.status === 401 && retry && !path.startsWith("/auth/")) {
    if (!refreshing) {
      refreshing = onUnauthorized().finally(() => {
        refreshing = null;
      });
    }
    const refreshed = await refreshing;
    if (refreshed) return apiRaw(path, options, false);
  }

  return response;
}

export async function download(path: string, filename: string) {
  const response = await apiRaw(path);
  if (!response.ok) {
    const body = await parseBody(response);
    throw new ApiError(
      messageFromBody(body, response.status),
      response.status,
    );
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function toQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}
