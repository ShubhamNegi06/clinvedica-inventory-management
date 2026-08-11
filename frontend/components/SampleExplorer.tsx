"use client";

/**
 * Shared sample browsing UI. Used by:
 *   - /inventories (master, no siteId prop = all accessible sites)
 *   - /inventories/[siteId] (a single site, admin/manager)
 *   - /samples (site user's own inventory — siteId is their own site_id)
 * Keeping this in one component means search/filter/export/bulk-select
 * behavior never drifts between the three contexts it's used in.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listSamples, deleteSample, startExport, downloadFromUrl, listFieldDefinitions } from "@/lib/resources";
import { ApiError } from "@/lib/api";
import { useTaskPolling } from "@/lib/useTaskPolling";
import type { ExportTaskResult, FieldDefinition, FieldFilter, Sample } from "@/lib/types";
import { FieldFilterInput } from "./FieldFilterInput";

export function SampleExplorer({ siteId, title }: { siteId?: string; title: string }) {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [fieldDefs, setFieldDefs] = useState<FieldDefinition[]>([]);
  const [filters, setFilters] = useState<FieldFilter[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportTaskId, setExportTaskId] = useState<string | null>(null);
  const exportTask = useTaskPolling<ExportTaskResult>(exportTaskId);
  const router = useRouter();
  const pageSize = 25;

  useEffect(() => {
    listFieldDefinitions().then(setFieldDefs);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listSamples({
        site_id: siteId,
        search: search || undefined,
        field_filters: filters.length ? filters : undefined,
        page,
        page_size: pageSize,
      });
      setSamples(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load samples.");
    } finally {
      setLoading(false);
    }
  }, [siteId, search, filters, page]);

  useEffect(() => {
    load();
  }, [load]);

  // Once the export task succeeds, trigger the browser download
  // automatically — this is the "for exports, automatically provide the
  // download when the task completes" requirement.
  useEffect(() => {
    if (exportTask.status === "SUCCESS" && exportTask.result) {
      downloadFromUrl(exportTask.result.download_url, exportTask.result.file_name);
    }
  }, [exportTask.status, exportTask.result]);

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    if (!confirm(`Delete ${selected.size} selected sample(s)? This cannot be undone.`)) return;
    await Promise.all(Array.from(selected).map((id) => deleteSample(id)));
    setSelected(new Set());
    await load();
  }

  async function handleExport() {
    setError(null);
    try {
      const { task_id } = await startExport({
        site_id: siteId,
        search: search || undefined,
        field_filters: filters.length ? filters : undefined,
      });
      setExportTaskId(task_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start export.");
    }
  }

  const addSampleHref = siteId ? `/samples/new?site_id=${siteId}` : "/samples/new";
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const typeOfTissueField = fieldDefs.find((f) => f.field_key === "type-of-tissue");
  const exportButtonLabel =
    exportTask.status === "PENDING" || exportTask.status === "STARTED"
      ? "Preparing export…"
      : "Export to Excel";

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{title}</h1>
          <p className="mt-1 text-sm text-gray-500">{total} sample{total === 1 ? "" : "s"}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {selected.size > 0 && (
            <button
              onClick={handleBulkDelete}
              className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100"
            >
              Delete {selected.size} selected
            </button>
          )}
          <button
            onClick={handleExport}
            disabled={exportTask.isRunning}
            className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
          >
            {exportButtonLabel}
          </button>
          <Link
            href={siteId ? `/bulk-upload?site_id=${siteId}` : "/bulk-upload"}
            className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Bulk Upload
          </Link>
          <Link
            href={addSampleHref}
            className="rounded-lg bg-brand-gradient px-4 py-2 text-sm font-medium text-white shadow-sm hover:opacity-95"
          >
            + Add Sample
          </Link>
        </div>
      </div>

      {exportTask.status === "FAILURE" && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          Export failed: {exportTask.error}
        </div>
      )}

      <div className="mb-4 space-y-3">
        <input
          value={search}
          onChange={(e) => {
            setPage(1);
            setSearch(e.target.value);
          }}
          placeholder="Search Subject ID or Sample ID…"
          className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        {fieldDefs.length > 0 && (
          <FieldFilterInput
            fields={fieldDefs}
            filters={filters}
            onChange={(f) => {
              setPage(1);
              setFilters(f);
            }}
          />
        )}
      </div>

      {error && <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="w-10 px-5 py-3">
                <input
                  type="checkbox"
                  checked={selected.size > 0 && selected.size === samples.length}
                  onChange={(e) =>
                    setSelected(e.target.checked ? new Set(samples.map((s) => s.id)) : new Set())
                  }
                />
              </th>
              <th className="px-5 py-3">Subject ID</th>
              <th className="px-5 py-3">Sample ID</th>
              {typeOfTissueField && <th className="px-5 py-3">Type of Tissue</th>}
              <th className="px-5 py-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-gray-400">Loading…</td>
              </tr>
            )}
            {!loading && samples.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-gray-400">No samples found.</td>
              </tr>
            )}
            {samples.map((sample) => (
              <tr key={sample.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                <td className="px-5 py-3" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected.has(sample.id)}
                    onChange={() => toggleSelected(sample.id)}
                  />
                </td>
                <td
                  className="cursor-pointer px-5 py-3 font-medium text-gray-900"
                  onClick={() => router.push(`/samples/${sample.id}`)}
                >
                  {sample.subject_id}
                </td>
                <td className="cursor-pointer px-5 py-3 text-gray-700" onClick={() => router.push(`/samples/${sample.id}`)}>
                  {sample.sample_id}
                </td>
                {typeOfTissueField && (
                  <td className="px-5 py-3 text-gray-500">
                    {String(sample.custom_fields["type-of-tissue"] ?? "—")}
                  </td>
                )}
                <td className="px-5 py-3 text-gray-400">{new Date(sample.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
