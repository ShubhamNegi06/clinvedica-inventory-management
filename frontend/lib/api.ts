/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Auth model (replaces the old Supabase-session-based version):
 *   - The ACCESS token lives in memory only (a module-level variable
 *     here, mirrored into React state by AuthContext for re-renders) —
 *     never localStorage/sessionStorage, so it isn't reachable by an
 *     XSS payload reading browser storage.
 *   - The REFRESH token lives in an httpOnly cookie set by the backend
 *     (POST /auth/login, /auth/refresh) — client-side JS can never read
 *     it at all, only the browser sends it automatically on requests to
 *     /auth/* (see the cookie's `path` in the backend's auth routes).
 *   - Every request attaches the in-memory access token as a Bearer
 *     header. On a 401, this module makes ONE attempt to silently
 *     refresh (POST /auth/refresh, relying on the cookie) and retries
 *     the original request once with the new token — if THAT also
 *     fails, the caller sees the error and AuthContext's session state
 *     clears, redirecting to /login.
 *
 * `credentials: "include"` is set on every request so the refresh
 * cookie is sent/received correctly even though frontend and backend
 * are different origins in most deployments — the backend's CORS config
 * already allows credentials for explicit origins (never "*").
 */
import type { AppUser, ApiErrorPayload } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  errorCode: string;
  field?: string;
  rowErrors?: ApiErrorPayload["row_errors"];
  status: number;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.status = status;
    this.errorCode = payload.error_code;
    this.field = payload.field;
    this.rowErrors = payload.row_errors;
  }
}

// --- In-memory access token -------------------------------------------

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

// --- Silent refresh ------------------------------------------------------

interface RefreshResult {
  access_token: string;
  expires_in_minutes: number;
  user: AppUser;
}

let inFlightRefresh: Promise<RefreshResult | null> | null = null;

/**
 * Calls POST /auth/refresh directly (NOT via apiRequest, to avoid
 * recursing into the 401-retry logic below). Deduplicates concurrent
 * callers into a single in-flight request — if five API calls all 401
 * at once, we don't want five simultaneous refresh attempts racing each
 * other and rotating the refresh token five times.
 */
export async function refreshAccessToken(): Promise<RefreshResult | null> {
  if (inFlightRefresh) return inFlightRefresh;

  inFlightRefresh = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        setAccessToken(null);
        return null;
      }
      const data: RefreshResult = await response.json();
      setAccessToken(data.access_token);
      return data;
    } catch {
      setAccessToken(null);
      return null;
    } finally {
      inFlightRefresh = null;
    }
  })();

  return inFlightRefresh;
}

// --- Core request wrapper -------------------------------------------------

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  isFormData?: boolean;
  query?: Record<string, string | number | string[] | undefined>;
  /** Internal: prevents infinite retry loops. Callers never set this. */
  _isRetry?: boolean;
}

function buildQueryString(query?: RequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) continue;
    if (Array.isArray(value)) {
      value.forEach((v) => params.append(key, v));
    } else {
      params.append(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  let body: BodyInit | undefined;
  if (options.body !== undefined) {
    if (options.isFormData) {
      body = options.body as FormData; // browser sets multipart boundary itself
    } else {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}${buildQueryString(options.query)}`, {
    method: options.method || "GET",
    headers,
    body,
    credentials: "include",
  });

  // One silent-refresh-and-retry attempt on 401 — covers the common case
  // of an access token expiring mid-session without forcing a full
  // re-login as long as the refresh cookie is still valid.
  if (response.status === 401 && !options._isRetry && !path.startsWith("/auth/")) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiRequest<T>(path, { ...options, _isRetry: true });
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : null;

  if (!response.ok) {
    throw new ApiError(
      response.status,
      data ?? { error_code: "unknown_error", message: `Request failed with status ${response.status}` }
    );
  }

  return data as T;
}

/** For endpoints that stream a file (Excel export download) rather than return JSON. */
export async function apiDownload(path: string, query?: RequestOptions["query"]): Promise<Blob> {
  const headers: Record<string, string> = {};
  if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  let response = await fetch(`${API_BASE_URL}${path}${buildQueryString(query)}`, {
    headers,
    credentials: "include",
  });

  if (response.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const retryHeaders: Record<string, string> = { Authorization: `Bearer ${refreshed.access_token}` };
      response = await fetch(`${API_BASE_URL}${path}${buildQueryString(query)}`, {
        headers: retryHeaders,
        credentials: "include",
      });
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data ?? { error_code: "unknown_error", message: "Download failed" });
  }
  return response.blob();
}
