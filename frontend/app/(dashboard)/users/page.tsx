"use client";

import { useEffect, useState, FormEvent } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { RoleGate } from "@/components/RoleGate";
import { Modal } from "@/components/Modal";
import { Field, TextInput, Select } from "@/components/FormFields";
import {
  listUsers,
  createUser,
  listSites,
  deleteUser,
  sendPasswordReset,
  setTemporaryPassword,
} from "@/lib/resources";
import { ApiError } from "@/lib/api";
import type { AppUser, Site, UserRole } from "@/lib/types";
import { useAuth } from "@/lib/authContext";

const ROLE_LABELS: Record<UserRole, string> = {
  it_admin: "IT Admin",
  inventory_manager: "Inventory Manager",
  site_user: "Site User",
};

function UsersPageContent() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AppUser[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [tempPasswordFor, setTempPasswordFor] = useState<{ email: string; password: string } | null>(null);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const searchParams = useSearchParams();
  const router = useRouter();

  // Inventory Managers cannot create/manage IT Admin accounts — this is
  // enforced server-side too (see backend app/services/user_service.py),
  // this just keeps the UI from offering an option that would 403.
  const isManager = currentUser?.role === "inventory_manager";
  const assignableRoles: UserRole[] = isManager
    ? ["inventory_manager", "site_user"]
    : ["it_admin", "inventory_manager", "site_user"];

  const [form, setForm] = useState({
    email: "",
    full_name: "",
    role: "site_user" as UserRole,
    site_id: "",
  });

  async function loadData() {
    setLoading(true);
    try {
      const [u, s] = await Promise.all([listUsers(), listSites()]);
      setUsers(u);
      setSites(s);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (searchParams.get("create") === "1") setModalOpen(true);
  }, [searchParams]);

  function closeModal() {
    setModalOpen(false);
    setFormError(null);
    router.replace("/users");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    setSuccessMsg(null);
    try {
      await createUser({
        email: form.email,
        full_name: form.full_name,
        role: form.role,
        site_id: form.role === "site_user" ? form.site_id : undefined,
      });
      setSuccessMsg(`Invite sent to ${form.email}.`);
      setForm({ email: "", full_name: "", role: "site_user", site_id: "" });
      closeModal();
      await loadData();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Failed to create user.");
    } finally {
      setSubmitting(false);
    }
  }

  function canManage(target: AppUser): boolean {
    // Mirrors the backend rule: Managers cannot act on IT Admin accounts.
    if (isManager && target.role === "it_admin") return false;
    return true;
  }

  async function handleDelete(target: AppUser) {
    if (target.id === currentUser?.id) return; // safety net; backend also rejects this
    if (!confirm(`Delete ${target.full_name} (${target.email})? This cannot be undone.`)) return;
    setBusyUserId(target.id);
    setActionError(null);
    try {
      await deleteUser(target.id);
      await loadData();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to delete user.");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleSendReset(target: AppUser) {
    setBusyUserId(target.id);
    setActionError(null);
    setSuccessMsg(null);
    try {
      const res = await sendPasswordReset(target.id);
      setSuccessMsg(res.message);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to send reset email.");
    } finally {
      setBusyUserId(null);
    }
  }

  async function handleSetTempPassword(target: AppUser) {
    if (!confirm(`Set a temporary password for ${target.full_name}? Their current password will stop working immediately.`)) return;
    setBusyUserId(target.id);
    setActionError(null);
    try {
      const res = await setTemporaryPassword(target.id);
      setTempPasswordFor({ email: target.email, password: res.temporary_password });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to set temporary password.");
    } finally {
      setBusyUserId(null);
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Manage Users</h1>
          <p className="mt-1 text-sm text-gray-500">
            {isManager
              ? "Create Inventory Managers and Site Users. IT Admin accounts are managed by an IT Admin."
              : "Create IT Admins, Inventory Managers, and Site Users."}
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded-lg bg-brand-gradient px-4 py-2 text-sm font-medium text-white shadow-sm hover:opacity-95"
        >
          + Create User
        </button>
      </div>

      {successMsg && (
        <div className="mb-4 rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{successMsg}</div>
      )}
      {actionError && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{actionError}</div>
      )}

      <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-5 py-3">Name</th>
              <th className="px-5 py-3">Email</th>
              <th className="px-5 py-3">Role</th>
              <th className="px-5 py-3">Site</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="px-5 py-6 text-center text-gray-400">Loading…</td>
              </tr>
            )}
            {!loading && users.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-6 text-center text-gray-400">No users yet.</td>
              </tr>
            )}
            {users.map((u) => {
              const manageable = canManage(u);
              const isSelf = u.id === currentUser?.id;
              const busy = busyUserId === u.id;
              return (
                <tr key={u.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                  <td className="px-5 py-3 font-medium text-gray-900">
                    {u.full_name}
                    {isSelf && <span className="ml-2 text-xs text-gray-400">(you)</span>}
                  </td>
                  <td className="px-5 py-3 text-gray-500">{u.email}</td>
                  <td className="px-5 py-3">
                    <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
                      {ROLE_LABELS[u.role]}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500">
                    {sites.find((s) => s.id === u.site_id)?.name || "—"}
                  </td>
                  <td className="px-5 py-3">
                    <span className={u.is_active ? "text-green-600" : "text-gray-400"}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    {!manageable ? (
                      <span className="text-xs text-gray-400">—</span>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        <button
                          disabled={busy}
                          onClick={() => handleSendReset(u)}
                          className="text-xs font-medium text-brand hover:underline disabled:opacity-50"
                        >
                          Reset Password
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => handleSetTempPassword(u)}
                          className="text-xs font-medium text-amber-700 hover:underline disabled:opacity-50"
                        >
                          Set Temp Password
                        </button>
                        {!isSelf && (
                          <button
                            disabled={busy}
                            onClick={() => handleDelete(u)}
                            className="text-xs font-medium text-red-600 hover:underline disabled:opacity-50"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <Modal open={modalOpen} onClose={closeModal} title="Create User">
        <form onSubmit={handleSubmit}>
          <Field label="Full Name">
            <TextInput
              required
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            />
          </Field>
          <Field label="Email">
            <TextInput
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>
          <Field label="Role">
            <Select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value as UserRole, site_id: "" })}
            >
              {assignableRoles.map((role) => (
                <option key={role} value={role}>
                  {ROLE_LABELS[role]}
                </option>
              ))}
            </Select>
          </Field>
          {form.role === "site_user" && (
            <Field label="Site">
              <Select
                required
                value={form.site_id}
                onChange={(e) => setForm({ ...form, site_id: e.target.value })}
              >
                <option value="">Select a site…</option>
                {sites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}

          {formError && <p className="mb-4 text-sm text-red-600">{formError}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-brand-gradient px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-60"
          >
            {submitting ? "Sending invite…" : "Create User"}
          </button>
          <p className="mt-3 text-xs text-gray-400">
            The user will receive an email invite to set their own password.
          </p>
        </form>
      </Modal>

      <Modal
        open={tempPasswordFor !== null}
        onClose={() => setTempPasswordFor(null)}
        title="Temporary Password Set"
      >
        {tempPasswordFor && (
          <div>
            <p className="mb-4 text-sm text-gray-600">
              Share this password with <strong>{tempPasswordFor.email}</strong> directly (in person, phone, etc.).
              It will not be shown again — copy it now.
            </p>
            <div className="mb-4 flex items-center justify-between rounded-lg bg-gray-100 px-4 py-3 font-mono text-sm">
              <span>{tempPasswordFor.password}</span>
              <button
                onClick={() => navigator.clipboard.writeText(tempPasswordFor.password)}
                className="ml-3 text-xs font-medium text-brand hover:underline"
              >
                Copy
              </button>
            </div>
            <button
              onClick={() => setTempPasswordFor(null)}
              className="w-full rounded-lg bg-brand-gradient px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95"
            >
              Done
            </button>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default function UsersPage() {
  return (
    <RoleGate allow={["it_admin", "inventory_manager"]}>
      <UsersPageContent />
    </RoleGate>
  );
}
