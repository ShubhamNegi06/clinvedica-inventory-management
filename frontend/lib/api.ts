/**
 * Thin fetch wrapper around the FastAPI backend.
 *
 * Every call attaches the current Supabase session's access token as a
 * Bearer header, and every non-2xx response is converted into a typed
 * `ApiError` carrying the backend's structured error shape
 * ({ error_code, message, field }) — callers can branch on `field` to
 * highlight the exact form input that failed (e.g. duplicate
 * sample_id), matching the UX already proven out in v1.
 */
import { supabase } from "./supabaseClient";
import type { ApiErrorPayload } from "./types";

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

async function getAuthHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  isFormData?: boolean;
  query?: Record<string, string | number | string[] | undefined>;
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
  const authHeader = await getAuthHeader();
  const headers: Record<string, string> = { ...authHeader };

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
  });

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

/** For endpoints that stream a file (Excel export) rather than return JSON. */
export async function apiDownload(path: string, query?: RequestOptions["query"]): Promise<Blob> {
  const authHeader = await getAuthHeader();
  const response = await fetch(`${API_BASE_URL}${path}${buildQueryString(query)}`, {
    headers: authHeader,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(response.status, data ?? { error_code: "unknown_error", message: "Download failed" });
  }
  return response.blob();
}
