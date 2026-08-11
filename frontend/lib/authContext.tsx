"use client";

/**
 * AuthProvider now owns the whole client-side session lifecycle directly
 * (replacing the earlier Supabase-session-based version):
 *   - On mount, attempts a silent refresh (POST /auth/refresh, relying
 *     on the httpOnly cookie) to restore a session without requiring
 *     re-login on every page load/reload.
 *   - Holds the access token in memory via lib/api.ts's
 *     setAccessToken/getAccessToken — never in localStorage.
 *   - login()/logout() call the new FastAPI endpoints directly.
 */
import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getAccessToken, setAccessToken, refreshAccessToken } from "./api";
import { login as apiLogin, logout as apiLogout, getCurrentUser } from "./resources";
import type { AppUser } from "./types";

interface AuthContextValue {
  user: AppUser | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AppUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const restoreSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // If we already have an access token in memory (e.g. just logged
      // in), skip the silent-refresh round trip and just fetch the
      // profile. Otherwise (fresh page load), try to silently restore a
      // session from the refresh cookie.
      if (!getAccessToken()) {
        const refreshed = await refreshAccessToken();
        if (!refreshed) {
          setUser(null);
          return;
        }
        setUser(refreshed.user);
        return;
      }
      const profile = await getCurrentUser();
      setUser(profile);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load your account.");
      setUser(null);
      setAccessToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    restoreSession();
  }, [restoreSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      const profile = await apiLogin(email, password);
      setUser(profile);
    },
    []
  );

  const signOut = useCallback(async () => {
    await apiLogout().catch(() => {
      // Logout should always succeed from the user's point of view even
      // if the network call fails — clear local state regardless.
    });
    setUser(null);
    router.replace("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, error, login, signOut, refresh: restoreSession }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
