"use client";

import { useEffect, useState, ChangeEvent } from "react";
import { useSearchParams } from "next/navigation";
import { RoleGate } from "@/components/RoleGate";
import { Field, Select } from "@/components/FormFields";
import { listSites, startBulkIngest } from "@/lib/resources";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/authContext";
import { useTaskPolling } from "@/lib/useTaskPolling";
import type { BulkIngestTaskResult, Site } from "@/lib/types";

function BulkUploadContent() {
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const isManagerOrAdmin = user?.role === "it_admin" || user?.role === "inventory_manager";

  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState(searchParams.get("site_id") ?? user?.site_id ?? "");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const task = useTaskPolling<BulkIngestTaskResult>(taskId);

  useEffect(() => {
    if (isManagerOrAdmin) listSites().then(setSites);
  }, [isManagerOrAdmin]);

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !siteId) return;
    setStartError(null);
    try {
      // Starts the Celery task and gets a task ID back immediately —
      // parsing/validating up to 5,000 rows happens in the background,
      // not on this request. The file input is disabled while a task is
      // in flight (task.isRunning below) to prevent duplicate submissions.
      const { task_id } = await startBulkIngest(siteId, file);
      setTaskId(task_id);
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : "Failed to start bulk upload.");
    } finally {
      e.target.value = "";
    }
  }

  const result = task.status === "SUCCESS" ? task.result : null;
  const uploadStageLabel =
    task.status === "PENDING"
      ? "Queued…"
      : task.status === "STARTED"
      ? task.progress?.stage === "parsing_file"
        ? "Parsing and validating rows…"
        : "Processing…"
      : "Click to select an .xlsx file";

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-2xl font-semibold text-gray-900">Bulk Upload</h1>
      <p className="mb-6 text-sm text-gray-500">
        Upload the Clinvedica Excel template exactly as-is — column headers must match the template
        (<code className="rounded bg-gray-100 px-1">Subject ID</code>,{" "}
        <code className="rounded bg-gray-100 px-1">Sample ID</code>,{" "}
        <code className="rounded bg-gray-100 px-1">Type of Tissue</code>, etc.). Both the{" "}
        <strong>Prospective</strong> and <strong>Remnant</strong> sheets are read automatically if both
        are present. Processing happens in the background — you can navigate away and come back.
      </p>

      <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
        {isManagerOrAdmin && (
          <Field label="Site">
            <Select value={siteId} onChange={(e) => setSiteId(e.target.value)} disabled={task.isRunning}>
              <option value="">Select a site…</option>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
        )}

        <label
          className={
            "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center " +
            (siteId && !task.isRunning ? "border-gray-200 hover:border-brand/40" : "cursor-not-allowed border-gray-100 opacity-50")
          }
        >
          <p className="text-sm font-medium text-gray-700">{uploadStageLabel}</p>
          <p className="mt-1 text-xs text-gray-400">Up to 5,000 rows per file, across all sheets</p>
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={handleFile}
            disabled={!siteId || task.isRunning}
            className="hidden"
          />
        </label>
      </div>

      {startError && <div className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{startError}</div>}

      {task.status === "FAILURE" && (
        <div className="mt-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          Bulk upload failed: {task.error}
        </div>
      )}

      {result && (
        <div className="mt-6 rounded-2xl border border-gray-100 bg-white p-6 shadow-sm">
          {!result.success ? (
            <p className="text-sm font-semibold text-red-700">{result.message || "Bulk upload failed."}</p>
          ) : (
            <p className="mb-3 text-sm font-semibold text-green-700">
              {result.created_count} sample{result.created_count === 1 ? "" : "s"} created successfully.
            </p>
          )}
          {result.row_errors && result.row_errors.length > 0 && (
            <>
              <p className="mb-2 mt-3 text-sm font-semibold text-red-700">
                {result.row_errors.length} row{result.row_errors.length === 1 ? "" : "s"} failed:
              </p>
              <ul className="max-h-64 space-y-1 overflow-y-auto text-xs text-gray-600">
                {result.row_errors.map((re, i) => (
                  <li key={i} className="rounded bg-red-50 px-2 py-1">
                    {re.sheet ? `[${re.sheet}] ` : ""}Row {re.row}
                    {re.sample_id ? ` (${re.sample_id})` : ""}: {re.error}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function BulkUploadPage() {
  return (
    <RoleGate allow={["it_admin", "inventory_manager", "site_user"]}>
      <BulkUploadContent />
    </RoleGate>
  );
}
