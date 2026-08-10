"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/authContext";
import { getDashboardStats } from "@/lib/resources";
import type { DashboardStats } from "@/lib/types";
import { StatCard } from "@/components/StatCard";
import { ApiError } from "@/lib/api";

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load dashboard stats."))
      .finally(() => setLoading(false));
  }, []);

  const isManagerOrAdmin = user?.role === "it_admin" || user?.role === "inventory_manager";

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">
            {user?.role === "site_user" ? "Your Inventory" : "Overview"}
          </h1>
          <p className="mt-1 text-sm text-gray-500">Welcome back, {user?.full_name}.</p>
        </div>

        {isManagerOrAdmin && (
          <div className="flex gap-3">
            <Link
              href="/users?create=1"
              className="rounded-lg bg-brand-gradient px-4 py-2 text-sm font-medium text-white shadow-sm hover:opacity-95"
            >
              + Create User
            </Link>
            <Link
              href="/sites?create=1"
              className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              + Create Site
            </Link>
          </div>
        )}
      </div>

      {loading && <p className="text-sm text-gray-500">Loading stats…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {stats && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {stats.total_sites !== null && <StatCard label="Total Sites" value={stats.total_sites} />}
          {stats.total_users !== null && <StatCard label="Total Users" value={stats.total_users} />}
          <StatCard label="Total Samples" value={stats.total_samples} accent />
          <StatCard label="Total Reports" value={stats.total_reports} accent />
        </div>
      )}
    </div>
  );
}
