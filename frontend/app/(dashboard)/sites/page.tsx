"use client";

import { useEffect, useState, FormEvent } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { RoleGate } from "@/components/RoleGate";
import { Modal } from "@/components/Modal";
import { Field, TextInput, Select } from "@/components/FormFields";
import { listSites, createSite } from "@/lib/resources";
import { ApiError } from "@/lib/api";
import type { Site } from "@/lib/types";
import { useAuth } from "@/lib/authContext";

function SitesPageContent() {
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const { user } = useAuth();
  const searchParams = useSearchParams();
  const router = useRouter();

  const [form, setForm] = useState({
    name: "",
    code: "",
    site_type: "partner_site" as "partner_site" | "manager_owned",
    contact_name: "",
    contact_email: "",
    contact_phone: "",
    address: "",
  });

  async function loadSites() {
    setLoading(true);
    try {
      setSites(await listSites());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSites();
  }, []);

  useEffect(() => {
    if (searchParams.get("create") === "1") setModalOpen(true);
  }, [searchParams]);

  function closeModal() {
    setModalOpen(false);
    setFormError(null);
    router.replace("/sites");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await createSite({
        ...form,
        contact_name: form.contact_name || undefined,
        contact_email: form.contact_email || undefined,
        contact_phone: form.contact_phone || undefined,
        address: form.address || undefined,
      });
      setForm({ name: "", code: "", site_type: "partner_site", contact_name: "", contact_email: "", contact_phone: "", address: "" });
      closeModal();
      await loadSites();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to create site.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Manage Sites</h1>
          <p className="mt-1 text-sm text-gray-500">
            Partner sites and, for Inventory Managers, your own independent inventories.
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded-lg bg-brand-gradient px-4 py-2 text-sm font-medium text-white shadow-sm hover:opacity-95"
        >
          + Create Site
        </button>
      </div>

      <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-5 py-3">Name</th>
              <th className="px-5 py-3">Code</th>
              <th className="px-5 py-3">Type</th>
              <th className="px-5 py-3">Contact</th>
              <th className="px-5 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-gray-400">Loading…</td>
              </tr>
            )}
            {!loading && sites.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-gray-400">No sites yet.</td>
              </tr>
            )}
            {sites.map((site) => (
              <tr key={site.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                <td className="px-5 py-3 font-medium text-gray-900">{site.name}</td>
                <td className="px-5 py-3 text-gray-500">{site.code}</td>
                <td className="px-5 py-3">
                  <span
                    className={
                      "rounded-full px-2.5 py-1 text-xs font-medium " +
                      (site.site_type === "manager_owned"
                        ? "bg-amber-50 text-amber-700"
                        : "bg-gray-100 text-gray-600")
                    }
                  >
                    {site.site_type === "manager_owned" ? "Manager Inventory" : "Partner Site"}
                  </span>
                </td>
                <td className="px-5 py-3 text-gray-500">{site.contact_email || "—"}</td>
                <td className="px-5 py-3">
                  <span className={site.is_active ? "text-green-600" : "text-gray-400"}>
                    {site.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={modalOpen} onClose={closeModal} title="Create Site">
        <form onSubmit={handleSubmit}>
          <Field label="Site Name">
            <TextInput required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Site Code">
            <TextInput
              required
              placeholder="e.g. AIIMS-DEL"
              value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })}
            />
          </Field>
          {user?.role === "inventory_manager" && (
            <Field label="Site Type">
              <Select
                value={form.site_type}
                onChange={(e) => setForm({ ...form, site_type: e.target.value as "partner_site" | "manager_owned" })}
              >
                <option value="partner_site">Partner Site (hospital / lab)</option>
                <option value="manager_owned">My Own Inventory</option>
              </Select>
            </Field>
          )}
          <Field label="Contact Name">
            <TextInput value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} />
          </Field>
          <Field label="Contact Email">
            <TextInput
              type="email"
              value={form.contact_email}
              onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
            />
          </Field>
          <Field label="Contact Phone">
            <TextInput value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
          </Field>
          <Field label="Address">
            <TextInput value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </Field>

          {formError && <p className="mb-4 text-sm text-red-600">{formError}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-brand-gradient px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-60"
          >
            {submitting ? "Creating…" : "Create Site"}
          </button>
        </form>
      </Modal>
    </div>
  );
}

export default function SitesPage() {
  return (
    <RoleGate allow={["it_admin", "inventory_manager"]}>
      <SitesPageContent />
    </RoleGate>
  );
}
