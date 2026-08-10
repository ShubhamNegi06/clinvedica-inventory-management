"use client";

import { RoleGate } from "@/components/RoleGate";
import { SampleExplorer } from "@/components/SampleExplorer";
import { useAuth } from "@/lib/authContext";

function MyInventoryContent() {
  const { user } = useAuth();
  // Site Users are always scoped to their own site — the backend enforces
  // this regardless, but passing it explicitly here means the UI never
  // even attempts to render a site selector for this role.
  return <SampleExplorer siteId={user?.site_id ?? undefined} title="My Inventory" />;
}

export default function SamplesPage() {
  return (
    <RoleGate allow={["site_user"]}>
      <MyInventoryContent />
    </RoleGate>
  );
}
