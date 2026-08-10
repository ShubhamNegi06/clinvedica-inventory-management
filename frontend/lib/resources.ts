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

// --- Samples ---
export interface SampleListParams {
  site_id?: string;
  tags?: string[];
  search?: string;
  page?: number;
  page_size?: number;
}
export const listSamples = (params: SampleListParams = {}) =>
  apiRequest<SampleListResponse>("/samples", { query: { ...params } });

export const getSample = (sampleId: string) => apiRequest<Sample>(`/samples/${sampleId}`);

export const createSample = (payload: {
  site_id: string;
  subject_id: string;
  sample_id: string;
  sample_type?: string;
  tags?: string[];
  custom_fields?: Record<string, unknown>;
}) => apiRequest<Sample>("/samples", { method: "POST", body: payload });

export const updateSample = (
  sampleId: string,
  payload: Partial<{
    subject_id: string;
    sample_id: string;
    sample_type: string;
    tags: string[];
    custom_fields: Record<string, unknown>;
  }>
) => apiRequest<Sample>(`/samples/${sampleId}`, { method: "PATCH", body: payload });

export const deleteSample = (sampleId: string) =>
  apiRequest<void>(`/samples/${sampleId}`, { method: "DELETE" });

export const bulkIngestSamples = (siteId: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<{
    created_count: number;
    created_sample_ids: string[];
    row_errors: Array<{ row: number; error: string; sample_id?: string }>;
  }>(`/samples/bulk-ingest/${siteId}`, { method: "POST", body: formData, isFormData: true });
};

export const exportSamples = (params: SampleListParams = {}) =>
  apiDownload("/samples/export", { ...params });

// --- Reports ---
export const listReportsForSample = (sampleId: string) =>
  apiRequest<Report[]>(`/reports/by-sample/${sampleId}`);

export const uploadReport = (sampleId: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiRequest<Report>(`/reports/by-sample/${sampleId}`, {
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

export const getSubjectAutofill = (subjectCode: string) =>
  apiRequest<{ found: boolean; custom_fields: Record<string, unknown> }>(
    `/subjects/${encodeURIComponent(subjectCode)}/autofill`
  );
