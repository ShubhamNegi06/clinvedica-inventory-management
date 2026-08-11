/**
 * Resource-specific API functions. Route/component code should always
 * call these rather than `apiRequest` directly — keeps endpoint paths in
 * exactly one place.
 */
import { apiRequest, apiDownload } from "./api";
import type {
  AppUser,
  DashboardStats,
  FieldDefinition,
  FieldFilter,
  Report,
  Sample,
  SampleListResponse,
  Site,
  UserRole,
} from "./types";

// --- Auth ---
export const getCurrentUser = () => apiRequest<AppUser>("/auth/me");

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
  apiRequest<{ message: string }>(`/users/${userId}/send-password-reset`, { method: "POST" });
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

export const bulkIngestSamples = (siteId: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<{
    created_count: number;
    created_sample_ids: string[];
    row_errors: Array<{ sheet?: string; row: number; error: string; sample_id?: string }>;
  }>(`/samples/bulk-ingest/${siteId}`, { method: "POST", body: formData, isFormData: true });
};

export const exportSamples = (params: SampleListParams = {}) =>
  apiDownload("/samples/export", {
    site_id: params.site_id,
    field_filter: toFieldFilterQuery(params.field_filters),
    search: params.search,
  });

// --- Reports ---
export const listReportsForSample = (samplePk: string) =>
  apiRequest<Report[]>(`/reports/by-sample/${samplePk}`);

/**
 * Uploads one or more PDF reports in a SINGLE request — this is what
 * fixes "can only upload one report at a time": every selected file is
 * appended under the same "files" field and sent together, and the
 * backend validates/stores each independently so one bad file doesn't
 * block the rest.
 */
export const uploadReports = (samplePk: string, files: File[]) => {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return apiRequest<{
    uploaded: Report[];
    errors: Array<{ file_name: string; error: string }>;
  }>(`/reports/by-sample/${samplePk}`, {
    method: "POST",
    body: formData,
    isFormData: true,
  });
};

export const getReportDownloadUrl = (reportId: string) =>
  apiRequest<{ url: string; expires_in_seconds: number }>(`/reports/${reportId}/download-url`);

export const deleteReport = (reportId: string) =>
  apiRequest<void>(`/reports/${reportId}`, { method: "DELETE" });

// --- Field definitions ---
export const listFieldDefinitions = () => apiRequest<FieldDefinition[]>("/field-definitions");

// --- Subjects / autofill ---
export const getSubjectSuggestions = (q: string) =>
  apiRequest<{ suggestions: string[] }>("/subjects/suggestions", { query: { q } });

export const getSubjectAutofill = (subjectId: string) =>
  apiRequest<{ found: boolean; custom_fields: Record<string, unknown> }>(
    `/subjects/${encodeURIComponent(subjectId)}/autofill`
  );
