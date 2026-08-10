"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { RoleGate } from "@/components/RoleGate";
import { SectionCard } from "@/components/DynamicFieldGrid";
import { PdfViewer } from "@/components/PdfViewer";
import {
  getSample,
  deleteSample,
  listReportsForSample,
  uploadReport,
  getReportDownloadUrl,
  deleteReport,
  listFieldDefinitions,
} from "@/lib/resources";
import { groupFieldsBySections } from "@/lib/fieldSections";
import { ApiError } from "@/lib/api";
import type { Sample, Report, FieldDefinition } from "@/lib/types";
import type { FieldSection } from "@/lib/fieldSections";

function SampleDetailContent() {
  const params = useParams<{ sampleId: string }>();
  const router = useRouter();

  const [sample, setSample] = useState<Sample | null>(null);
  const [sections, setSections] = useState<FieldSection[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [activeReportUrl, setActiveReportUrl] = useState<{ url: string; name: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, defs, r] = await Promise.all([
        getSample(params.sampleId),
        listFieldDefinitions(),
        listReportsForSample(params.sampleId),
      ]);
      setSample(s);
      setSections(groupFieldsBySections(defs));
      setReports(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load sample.");
    } finally {
      setLoading(false);
    }
  }, [params.sampleId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDeleteSample() {
    if (!confirm("Delete this sample and all its reports? This cannot be undone.")) return;
    await deleteSample(params.sampleId);
    router.back();
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadReport(params.sampleId, file);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to upload report.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleView(report: Report) {
    const { url } = await getReportDownloadUrl(report.id);
    setActiveReportUrl({ url, name: report.file_name });
  }

  async function handleDeleteReport(report: Report) {
    if (!confirm(`Delete "${report.file_name}"?`)) return;
    await deleteReport(report.id);
    if (activeReportUrl?.name === report.file_name) setActiveReportUrl(null);
    await load();
  }

  if (loading) return <p className="text-sm text-gray-500">Loading…</p>;
  if (error && !sample) return <p className="text-sm text-red-600">{error}</p>;
  if (!sample) return null;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{sample.sample_id}</h1>
          <p className="mt-1 text-sm text-gray-500">Subject: {sample.subject_id}</p>
        </div>
        <button
          onClick={handleDeleteSample}
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
        >
          Delete Sample
        </button>
      </div>

      {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <SectionCard title="Sample Information">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Sample Type</p>
                <p className="font-medium text-gray-900">{sample.sample_type ?? "—"}</p>
              </div>
              <div>
                <p className="text-gray-500">Tags</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {sample.tags.length === 0 && <span className="text-gray-400">—</span>}
                  {sample.tags.map((t) => (
                    <span key={t} className="rounded-full bg-peach-50 px-2 py-0.5 text-xs text-brand">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          {sections.map((section) => {
            const populated = section.fields.filter((f) => sample.custom_fields[f.field_key]);
            if (populated.length === 0) return null;
            return (
              <SectionCard key={section.key} title={section.label} defaultOpen={false}>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  {populated.map((f) => (
                    <div key={f.field_key}>
                      <p className="text-gray-500">{f.field_label}</p>
                      <p className="font-medium text-gray-900">{String(sample.custom_fields[f.field_key])}</p>
                    </div>
                  ))}
                </div>
              </SectionCard>
            );
          })}
        </div>

        <div>
          <div className="mb-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-gray-900">Reports</p>
              <label className="cursor-pointer text-xs font-medium text-brand hover:underline">
                {uploading ? "Uploading…" : "+ Upload PDF"}
                <input type="file" accept="application/pdf" onChange={handleUpload} className="hidden" disabled={uploading} />
              </label>
            </div>
            {reports.length === 0 && <p className="text-sm text-gray-400">No reports uploaded yet.</p>}
            <ul className="space-y-2">
              {reports.map((r) => (
                <li key={r.id} className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2">
                  <button onClick={() => handleView(r)} className="truncate text-left text-sm text-gray-700 hover:text-brand">
                    {r.file_name}
                  </button>
                  <button
                    onClick={() => handleDeleteReport(r)}
                    className="ml-2 text-xs text-red-500 hover:text-red-700"
                    aria-label={`Delete ${r.file_name}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {activeReportUrl && <PdfViewer url={activeReportUrl.url} fileName={activeReportUrl.name} />}
        </div>
      </div>
    </div>
  );
}

export default function SampleDetailPage() {
  return (
    <RoleGate allow={["it_admin", "inventory_manager", "site_user"]}>
      <SampleDetailContent />
    </RoleGate>
  );
}
