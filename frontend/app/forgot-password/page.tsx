"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";
import { forgotPassword } from "@/lib/resources";
import { ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await forgotPassword(email);
      // Always show the same success state regardless of whether the
      // email exists — the backend deliberately returns an identical
      // generic message either way (see POST /auth/forgot-password).
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-peach-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 h-14 w-14 rounded-2xl bg-brand-gradient shadow-lg shadow-brand/20" />
          <h1 className="text-2xl font-semibold text-gray-900">Reset Your Password</h1>
          <p className="mt-1 text-sm text-gray-500">We&apos;ll email you a link to choose a new one.</p>
        </div>

        <div className="rounded-2xl border border-gray-100 bg-white p-8 shadow-sm">
          {submitted ? (
            <div className="text-center">
              <p className="text-sm text-gray-700">
                If an account exists for <strong>{email}</strong>, a password reset link has been sent.
              </p>
              <Link href="/login" className="mt-4 inline-block text-sm font-medium text-brand hover:underline">
                Back to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="mb-6">
                <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-gray-700">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  placeholder="you@clinvedica.com"
                />
              </div>

              {error && (
                <div className="mb-4 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-700">{error}</div>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-lg bg-brand-gradient px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:opacity-95 disabled:opacity-60"
              >
                {submitting ? "Sending…" : "Send Reset Link"}
              </button>

              <Link href="/login" className="mt-4 block text-center text-xs font-medium text-gray-400 hover:text-gray-600">
                Back to sign in
              </Link>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
