"use client";

/**
 * Shared sample browsing UI. Used by:
 *   - /inventories (master, no siteId prop = all accessible sites)
 *   - /inventories/[siteId] (a single site, admin/manager)
 *   - /samples (site user's own inventory — siteId is their own site_id)
 * Keeping this in one component means search/tag-filter/export/bulk-select
 * behavior never drifts between the three contexts it's used in.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listSamples, deleteSample, exportSamples } from "@/lib/resources";
import { ApiError } from "@/lib/api";
import type { Sample } from "@/lib/types";
import { TagFilterInput } from "./TagFilterInput";

export function SampleExplorer({ siteId, title }: { siteId?: string; title: string }) {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const router = useRouter();
  const pageSize = 25;

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listSamples({ site_id: siteId, search: search || undefined, tags: tags.length ? tags : undefined, page, page_size: pageSize });
      setSamples(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load samples.");
    } finally {
      setLoading(false);
    }
  }, [siteId, search, tags, page]);

  useEffect(() => {
    load();
  }, [load]);

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
    setExporting(true);
    try {
      const blob = await exportSamples({ site_id: siteId, search: search || undefined, tags: tags.length ? tags : undefined });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "specimen_inventory_export.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  const addSampleHref = siteId ? `/samples/new?site_id=${siteId}` : "/samples/new";
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

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
            disabled={exporting}
            className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
          >
            {exporting ? "Exporting…" : "Export to Excel"}
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

      <div className="mb-4 flex flex-wrap gap-3">
        <input
          value={search}
          onChange={(e) => {
            setPage(1);
            setSearch(e.target.value);
          }}
          placeholder="Search subject or sample code…"
          className="min-w-[240px] flex-1 rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        />
        <div className="min-w-[240px] flex-1">
          <TagFilterInput
            tags={tags}
            onChange={(t) => {
              setPage(1);
              setTags(t);
            }}
          />
        </div>
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
              <th className="px-5 py-3">Subject Code</th>
              <th className="px-5 py-3">Sample Code</th>
              <th className="px-5 py-3">Sample Type</th>
              <th className="px-5 py-3">Tags</th>
              <th className="px-5 py-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-5 py-6 text-center text-gray-400">Loading…</td>
              </tr>
            )}
            {!loading && samples.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-6 text-center text-gray-400">No samples found.</td>
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
                <td className="px-5 py-3 text-gray-500">{sample.sample_type || "—"}</td>
                <td className="px-5 py-3">
                  <div className="flex flex-wrap gap-1">
                    {sample.tags.map((t) => (
                      <span key={t} className="rounded-full bg-peach-50 px-2 py-0.5 text-xs text-brand">
                        {t}
                      </span>
                    ))}
                  </div>
                </td>
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
