"use client";

/**
 * AuthProvider resolves the Supabase session into our app-level `AppUser`
 * (role, site_id, etc.) via GET /auth/me, and exposes it through context.
 * This is the single source of truth every dashboard/layout reads from
 * to decide what to render and where to redirect.
 */
import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "./supabaseClient";
import { getCurrentUser } from "./resources";
import type { AppUser } from "./types";

interface AuthContextValue {
  user: AppUser | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AppUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const loadUser = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        setUser(null);
        return;
      }
      const profile = await getCurrentUser();
      setUser(profile);
    } catch (err) {
      // A verified Supabase session but a failed /auth/me call usually
      // means the account exists in Supabase Auth but was never
      // provisioned in our `users` table (or was deactivated) — surface
      // that clearly rather than silently redirecting to login.
      setError(err instanceof Error ? err.message : "Failed to load your account.");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
    const { data: subscription } = supabase.auth.onAuthStateChange(() => {
      loadUser();
    });
    return () => subscription.subscription.unsubscribe();
  }, [loadUser]);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setUser(null);
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, error, refresh: loadUser, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
