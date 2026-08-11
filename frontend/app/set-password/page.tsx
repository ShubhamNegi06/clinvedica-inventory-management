"use client";

/**
 * Catches BOTH the invite link (new account, first-time password set)
 * and the password-reset link (forgot-password / admin-triggered reset)
 * — both send the user here with ?token=...&purpose=invite|reset in the
 * URL. Much simpler than the old Supabase version: no magic-link session
 * detection needed, since our own opaque token is validated directly by
 * POST /auth/reset-password (same endpoint handles both purposes — see
 * that route's docstring for why one mechanism covers both).
 */
import { useState, FormEvent, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { resetPassword } from "@/lib/resources";
import { ApiError } from "@/lib/api";

function SetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const purpose = searchParams.get("purpose") === "invite" ? "invite" : "reset";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (!token) {
      setError("This link is missing its token. Request a new one.");
      return;
    }

    setSubmitting(true);
    try {
      await resetPassword(token, password);
      setSuccess(true);
      setTimeout(() => router.replace("/login"), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to set your password.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <div className="max-w-md rounded-2xl border border-red-100 bg-white p-8 text-center shadow-sm">
        <p className="text-sm font-medium text-red-700">This link is invalid.</p>
        <p className="mt-2 text-sm text-gray-500">
          Ask your administrator to send you a new invite or password reset email.
        </p>
      </div>
    );
  }

  if (success) {
    return (
      <div className="max-w-md rounded-2xl border border-green-100 bg-white p-8 text-center shadow-sm">
        <p className="text-sm font-medium text-green-700">Password set successfully.</p>
        <p className="mt-2 text-sm text-gray-500">Redirecting you to sign in…</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-4 h-14 w-14 rounded-2xl bg-brand-gradient shadow-lg shadow-brand/20" />
        <h1 className="text-2xl font-semibold text-gray-900">
          {purpose === "invite" ? "Set Your Password" : "Choose a New Password"}
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          {purpose === "invite"
            ? "Choose a password to finish setting up your account."
            : "Enter a new password for your account."}
        </p>
      </div>

      <form onSubmit={handleSubmit} className="rounded-2xl border border-gray-100 bg-white p-8 shadow-sm">
        <div className="mb-4">
          <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-gray-700">
            New Password
          </label>
          <input
            id="password"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
            placeholder="At least 8 characters"
          />
        </div>

        <div className="mb-6">
          <label htmlFor="confirmPassword" className="mb-1.5 block text-sm font-medium text-gray-700">
            Confirm Password
          </label>
          <input
            id="confirmPassword"
            type="password"
            required
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
          />
        </div>

        {error && <div className="mb-4 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-brand-gradient px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-60"
        >
          {submitting ? "Setting password…" : "Set Password & Continue"}
        </button>
      </form>
    </div>
  );
}

export default function SetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-peach-50 px-4">
      <Suspense fallback={<p className="text-sm text-gray-500">Loading…</p>}>
        <SetPasswordForm />
      </Suspense>
    </div>
  );
}
