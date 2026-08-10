"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { RoleGate } from "@/components/RoleGate";
import { listSites } from "@/lib/resources";
import type { Site } from "@/lib/types";

function InventoriesContent() {
  const [sites, setSites] = useState<Site[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listSites()
      .then(setSites)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">All Inventories</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse the aggregated Master Inventory, or drill into a specific site.
        </p>
      </div>

      <Link
        href="/inventories/master"
        className="mb-6 block rounded-2xl bg-brand-gradient p-6 text-white shadow-sm transition hover:opacity-95"
      >
        <p className="text-lg font-semibold">Master Inventory</p>
        <p className="mt-1 text-sm text-white/80">
          Every sample across every site and manager-owned inventory, in one searchable view.
        </p>
      </Link>

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">By Site</h2>
      {loading && <p className="text-sm text-gray-400">Loading sites…</p>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sites.map((site) => (
          <Link
            key={site.id}
            href={`/inventories/${site.id}`}
            className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm transition hover:border-brand/30 hover:shadow-md"
          >
            <div className="mb-2 flex items-center justify-between">
              <p className="font-medium text-gray-900">{site.name}</p>
              {site.site_type === "manager_owned" && (
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
                  My Inventory
                </span>
              )}
            </div>
            <p className="text-sm text-gray-500">{site.code}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function InventoriesPage() {
  return (
    <RoleGate allow={["it_admin", "inventory_manager"]}>
      <InventoriesContent />
    </RoleGate>
  );
}
