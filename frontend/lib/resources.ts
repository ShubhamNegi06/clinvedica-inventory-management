/**
 * Resource-specific API functions. Route/component code should always
 * call these rather than `apiRequest` directly — keeps endpoint paths in
 * exactly one place.
 */
import { apiRequest, setAccessToken } from "./api";
import type {
  AppUser,
  DashboardStats,
  FieldDefinition,
  FieldFilter,
  Report,
  Sample,
  SampleListResponse,
  Site,
  TaskEnqueuedResponse,
  TaskStatusResponse,
  UserRole,
} from "./types";

// --- Auth ---------------------------------------------------------------
// login/logout/refresh are the only calls that need `credentials:
// "include"` explicitly noted — apiRequest already sets that on every
// call, but these three are also the ones that actually cause the
// backend to set/clear the httpOnly refresh cookie.

export interface LoginResult {
  access_token: string;
  expires_in_minutes: number;
  user: AppUser;
}

export async function login(email: string, password: string): Promise<AppUser> {
  const result = await apiRequest<LoginResult>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
  setAccessToken(result.access_token);
  return result.user;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<void>("/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}

export const getCurrentUser = () => apiRequest<AppUser>("/auth/me");

export const forgotPassword = (email: string) =>
  apiRequest<{ message: string }>("/auth/forgot-password", { method: "POST", body: { email } });

export const resetPassword = (token: string, newPassword: string) =>
  apiRequest<{ message: string }>("/auth/reset-password", {
    method: "POST",
    body: { token, new_password: newPassword },
  });

// --- Dashboard ---
export const getDashboardStats = () => apiRequest<DashboardStats>("/dashboard/stats");

// --- Sites ---
export const listSites = () => apiRequest<Site[]>("/sites");
export const createSite = (payload: {
  name: string;
  code: string;
  site_type: "partner_site" | "manager_owned";
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  address?: string;
}) => apiRequest<Site>("/sites", { method: "POST", body: payload });

// --- Users ---
export const listUsers = () => apiRequest<AppUser[]>("/users");
export const createUser = (payload: {
  email: string;
  full_name: string;
  role: UserRole;
  site_id?: string;
}) => apiRequest<AppUser>("/users", { method: "POST", body: payload });
export const deleteUser = (userId: string) => apiRequest<void>(`/users/${userId}`, { method: "DELETE" });
export const sendPasswordReset = (userId: string) =>
  apiRequest<{ message: string; task_id?: string }>(`/users/${userId}/send-password-reset`, { method: "POST" });
export const setTemporaryPassword = (userId: string) =>
  apiRequest<{ temporary_password: string }>(`/users/${userId}/set-temporary-password`, { method: "POST" });

// --- Samples ---
// `field_filters` are key:value pairs against custom_fields (e.g.
// { field_key: "tumor-percent", value: "60" }), sent to the backend as
// repeated "field_filter=key:value" query params — NOT freeform tags.
export interface SampleListParams {
  site_id?: string;
  field_filters?: FieldFilter[];
  search?: string;
  page?: number;
  page_size?: number;
}

function toFieldFilterQuery(filters?: FieldFilter[]): string[] | undefined {
  if (!filters || filters.length === 0) return undefined;
  return filters.map((f) => `${f.field_key}:${f.value}`);
}

export const listSamples = (params: SampleListParams = {}) =>
  apiRequest<SampleListResponse>("/samples", {
    query: {
      site_id: params.site_id,
      field_filter: toFieldFilterQuery(params.field_filters),
      search: params.search,
      page: params.page,
      page_size: params.page_size,
    },
  });

export const getSample = (samplePk: string) => apiRequest<Sample>(`/samples/${samplePk}`);

export const createSample = (payload: {
  site_id: string;
  subject_id: string;
  sample_id: string;
  custom_fields?: Record<string, unknown>;
}) => apiRequest<Sample>("/samples", { method: "POST", body: payload });

export const updateSample = (
  samplePk: string,
  payload: Partial<{
    subject_id: string;
    sample_id: string;
    custom_fields: Record<string, unknown>;
  }>
) => apiRequest<Sample>(`/samples/${samplePk}`, { method: "PATCH", body: payload });

export const deleteSample = (samplePk: string) =>
  apiRequest<void>(`/samples/${samplePk}`, { method: "DELETE" });

/**
 * Starts a bulk-ingest Celery task and returns immediately with a task
 * ID — this no longer waits for the (potentially 5,000-row) import to
 * finish inline. Callers should poll getTaskStatus(task_id) — see
 * lib/useTaskPolling.ts for a ready-made hook.
 */
export const startBulkIngest = (siteId: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<TaskEnqueuedResponse>(`/samples/bulk-ingest/${siteId}`, {
    method: "POST",
    body: formData,
    isFormData: true,
  });
};

/** Starts an Excel export Celery task — poll getTaskStatus(task_id); the
 * result contains a signed download_url once status is SUCCESS. */
export const startExport = (params: SampleListParams = {}) =>
  apiRequest<TaskEnqueuedResponse>("/samples/export", {
    query: {
      site_id: params.site_id,
      field_filter: toFieldFilterQuery(params.field_filters),
      search: params.search,
    },
  });

// --- Reports ---
export const listReportsForSample = (samplePk: string) =>
  apiRequest<Report[]>(`/reports/by-sample/${samplePk}`);

/**
 * Starts a Celery task that uploads every selected PDF to R2 — this is
 * what fixes "can only upload one report at a time" AND moves the R2
 * I/O off the request thread. Poll getTaskStatus(task_id); the result
 * contains { uploaded: [...], errors: [...] } once status is SUCCESS.
 */
export const startReportUpload = (samplePk: string, files: File[]) => {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return apiRequest<TaskEnqueuedResponse>(`/reports/by-sample/${samplePk}`, {
    method: "POST",
    body: formData,
    isFormData: true,
  });
};

export const getReportDownloadUrl = (reportId: string) =>
  apiRequest<{ url: string; expires_in_seconds: number }>(`/reports/${reportId}/download-url`);

export const deleteReport = (reportId: string) =>
  apiRequest<void>(`/reports/${reportId}`, { method: "DELETE" });

// --- Tasks (generic polling) ---
export const getTaskStatus = (taskId: string) => apiRequest<TaskStatusResponse>(`/tasks/${taskId}`);

// --- Field definitions ---
export const listFieldDefinitions = () => apiRequest<FieldDefinition[]>("/field-definitions");

// --- Subjects / autofill ---
export const getSubjectSuggestions = (q: string) =>
  apiRequest<{ suggestions: string[] }>("/subjects/suggestions", { query: { q } });

export const getSubjectAutofill = (subjectId: string) =>
  apiRequest<{ found: boolean; custom_fields: Record<string, unknown> }>(
    `/subjects/${encodeURIComponent(subjectId)}/autofill`
  );

// --- Excel export file download (from a completed task's result URL) ---
export async function downloadFromUrl(url: string, filename: string): Promise<void> {
  // Signed R2 URLs are already authorized on their own — no auth headers
  // needed for this fetch, it's a plain cross-origin GET to R2.
  const blob = await fetch(url).then((r) => r.blob());
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objectUrl);
}
