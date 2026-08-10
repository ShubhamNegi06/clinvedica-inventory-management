"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useAuth } from "@/lib/authContext";
import type { UserRole } from "@/lib/types";

interface NavItem {
  href: string;
  label: string;
  roles: UserRole[];
}

// Single source of truth for navigation — visibility per role is declared
// right here rather than scattered `{role === 'x' && <Link/>}` checks
// throughout JSX.
const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", roles: ["it_admin", "inventory_manager", "site_user"] },
  { href: "/inventories", label: "All Inventories", roles: ["it_admin", "inventory_manager"] },
  { href: "/samples", label: "My Inventory", roles: ["site_user"] },
  { href: "/sites", label: "Manage Sites", roles: ["it_admin", "inventory_manager"] },
  { href: "/users", label: "Manage Users", roles: ["it_admin", "inventory_manager"] },
  { href: "/bulk-upload", label: "Bulk Upload", roles: ["it_admin", "inventory_manager", "site_user"] },
];

const ROLE_LABELS: Record<UserRole, string> = {
  it_admin: "IT Admin",
  inventory_manager: "Inventory Manager",
  site_user: "Site User",
};

export function Sidebar() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();

  if (!user) return null;
  const visibleItems = NAV_ITEMS.filter((item) => item.roles.includes(user.role));

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-shrink-0 flex-col border-r border-gray-100 bg-peach-50">
      <div className="flex items-center gap-3 px-6 py-6">
        <div className="h-9 w-9 rounded-xl bg-brand-gradient" />
        <div>
          <p className="text-sm font-semibold text-gray-900">Specimen Inventory</p>
          <p className="text-xs text-gray-500">Clin Vedica</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {visibleItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "block rounded-lg px-3 py-2.5 text-sm font-medium transition",
                active
                  ? "bg-brand-gradient text-white shadow-sm"
                  : "text-gray-600 hover:bg-white hover:text-gray-900"
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-gray-200 px-4 py-4">
        <p className="truncate text-sm font-medium text-gray-900">{user.full_name}</p>
        <p className="mb-3 text-xs text-gray-500">{ROLE_LABELS[user.role]}</p>
        <button
          onClick={signOut}
          className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-50"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
