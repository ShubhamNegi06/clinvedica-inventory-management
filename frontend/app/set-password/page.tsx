"use client";

/**
 * Catches the redirect from BOTH Supabase flows that land a user here:
 *   - Invite email (new account, first-time password set)
 *   - Password recovery email ("Reset Password" / "Set Temporary
 *     Password" admin actions redirect here too)
 *
 * Supabase's client (detectSessionInUrl: true, set in lib/supabaseClient.ts)
 * automatically parses the access token out of the URL fragment on load
 * and establishes a temporary session — that's what listening for
 * onAuthStateChange below is for. Once that session exists, the user can
 * call `updateUser({ password })` to set their real password, regardless
 * of which of the two flows got them here. This is why one page covers
 * both cases instead of two near-identical ones.
 */
import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function SetPasswordPage() {
  const [sessionReady, setSessionReady] = useState(false);
  const [checking, setChecking] = useState(true);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    // Covers the case where the session is already established by the
    // time this component mounts (fast parse).
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) setSessionReady(true);
      setChecking(false);
    });

    // Covers the case where detectSessionInUrl finishes parsing slightly
    // after mount — both PASSWORD_RECOVERY and SIGNED_IN events indicate
    // a usable session for setting a password.
    const { data: subscription } = supabase.auth.onAuthStateChange((event, session) => {
      if (session && (event === "PASSWORD_RECOVERY" || event === "SIGNED_IN" || event === "INITIAL_SESSION")) {
        setSessionReady(true);
        setChecking(false);
      }
    });

    return () => subscription.subscription.unsubscribe();
  }, []);

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

    setSubmitting(true);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    setSubmitting(false);

    if (updateError) {
      setError(updateError.message);
      return;
    }

    router.replace("/dashboard");
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-peach-50">
        <p className="text-sm text-gray-500">Verifying your link…</p>
      </div>
    );
  }

  if (!sessionReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-peach-50 px-4">
        <div className="max-w-md rounded-2xl border border-red-100 bg-white p-8 text-center shadow-sm">
          <p className="text-sm font-medium text-red-700">This link is invalid or has expired.</p>
          <p className="mt-2 text-sm text-gray-500">
            Ask your administrator to send you a new invite or password reset email.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-peach-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 h-14 w-14 rounded-2xl bg-brand-gradient shadow-lg shadow-brand/20" />
          <h1 className="text-2xl font-semibold text-gray-900">Set Your Password</h1>
          <p className="mt-1 text-sm text-gray-500">Choose a password to finish setting up your account.</p>
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
    </div>
  );
}
