"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { RoleGate } from "@/components/RoleGate";
import { SampleExplorer } from "@/components/SampleExplorer";
import { listSites } from "@/lib/resources";
import type { Site } from "@/lib/types";

function SiteInventoryContent() {
  const params = useParams<{ siteId: string }>();
  const isMaster = params.siteId === "master";
  const [site, setSite] = useState<Site | null>(null);

  useEffect(() => {
    if (isMaster) return;
    listSites().then((sites) => setSite(sites.find((s) => s.id === params.siteId) ?? null));
  }, [params.siteId, isMaster]);

  return (
    <SampleExplorer
      siteId={isMaster ? undefined : params.siteId}
      title={isMaster ? "Master Inventory" : site?.name ?? "Site Inventory"}
    />
  );
}

export default function SiteInventoryPage() {
  return (
    <RoleGate allow={["it_admin", "inventory_manager"]}>
      <SiteInventoryContent />
    </RoleGate>
  );
}
