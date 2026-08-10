/**
 * Types mirroring the backend's Pydantic schemas exactly. Keeping these
 * hand-in-sync (rather than codegen) is a deliberate trade-off for this
 * project's size — if the API surface grows much further, generating
 * these from the OpenAPI schema (openapi-typescript) would be worth it.
 */

export type UserRole = "it_admin" | "inventory_manager" | "site_user";

export type SiteType = "partner_site" | "manager_owned";

export type ReportType = "original" | "masked";

export type SampleType =
  | "ffpe"
  | "frozen_tumor"
  | "serum"
  | "plasma"
  | "whole_blood"
  | "other";

export interface AppUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  site_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Site {
  id: string;
  name: string;
  code: string;
  site_type: SiteType;
  owned_by_user_id: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  address: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Sample {
  id: string;
  site_id: string;
  subject_id: string;
  sample_id: string;
  sample_type: SampleType | null;
  tags: string[];
  custom_fields: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SampleListResponse {
  items: Sample[];
  total: number;
  page: number;
  page_size: number;
}

export interface Report {
  id: string;
  sample_id: string;
  site_id: string;
  file_name: string;
  file_size_bytes: number | null;
  content_type: string;
  report_type: ReportType;
  original_report_id: string | null;
  created_at: string;
}

export interface FieldDefinition {
  id: string;
  field_key: string;
  field_label: string;
  section: string;
  field_type: "text" | "number" | "date" | "select";
  display_order: number;
  is_autofill: boolean;
}

export interface DashboardStats {
  total_sites: number | null;
  total_users: number | null;
  total_samples: number;
  total_reports: number;
}

/** Uniform error shape returned by every backend endpoint (see app/main.py's exception handler). */
export interface ApiErrorPayload {
  error_code: string;
  message: string;
  field?: string;
  row_errors?: Array<{ row: number; error: string; sample_id?: string }>;
}

export const SECTION_ORDER = [
  "case_details",
  "demographic_details",
  "diagnosis_information",
  "sample_information",
  "serology_report",
  "treatment_detail",
  "biomarker_characterization",
] as const;

export const SECTION_LABELS: Record<string, string> = {
  case_details: "Case Details",
  demographic_details: "Demographic Details",
  diagnosis_information: "Diagnosis Information",
  sample_information: "Sample Information",
  serology_report: "Serology Report",
  treatment_detail: "Treatment Detail",
  biomarker_characterization: "Biomarker Characterization",
};
