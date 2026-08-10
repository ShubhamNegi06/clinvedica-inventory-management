"use client";

/**
 * Declarative role restriction for page content. This is a UX
 * convenience only — the REAL enforcement is server-side (FastAPI's
 * require_roles dependency), since a client-side check can always be
 * bypassed. This just avoids showing a Site User a management UI whose
 * buttons would all 403 anyway.
 */
import { ReactNode } from "react";
import { useAuth } from "@/lib/authContext";
import type { UserRole } from "@/lib/types";

export function RoleGate({ allow, children }: { allow: UserRole[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !allow.includes(user.role)) {
    return (
      <div className="rounded-xl border border-gray-100 bg-white p-8 text-center text-sm text-gray-500">
        You don&apos;t have access to this page.
      </div>
    );
  }
  return <>{children}</>;
}
