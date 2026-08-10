# Specimen Inventory — Frontend (v2)

Next.js 16 + TypeScript + Tailwind frontend for the Clinvedica Specimen
Inventory platform. Talks to Supabase Auth directly for login/session, and
to the FastAPI backend for everything else.

## Setup

```powershell
npm install
copy .env.example .env.local
# fill in NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY,
# NEXT_PUBLIC_API_BASE_URL (defaults to http://localhost:8000/api/v1)

npm run dev
```

Verified in this build environment:
- `npx tsc --noEmit` — passes clean
- `npm run build` — succeeds (Next.js 16.3.0, Turbopack), all 12 routes
  compile including dynamic `[siteId]` and `[sampleId]` routes

**Not yet verified against a real backend** — this was built and
type-checked against dummy env values only, since the sandbox has no
network path to your Supabase/R2/API instances. Test the full login →
dashboard → sample flow against a real staging backend before deploying.

## Structure

```
app/
  login/                    # Supabase Auth login page
  (dashboard)/              # route group: auth-gated, renders Sidebar
    dashboard/               # role-scoped stats (shared across all 3 roles)
    inventories/              # IT Admin / Inventory Manager: master + per-site
    samples/                  # Site User: own inventory; shared detail/new pages
    sites/                     # IT Admin / Inventory Manager: manage sites
    users/                     # IT Admin / Inventory Manager: manage users
    bulk-upload/                # Excel bulk ingestion, all roles
components/                 # shared UI (SampleExplorer, DynamicFieldGrid, etc.)
lib/                        # Supabase client, API wrapper, types, auth context
```

## Notable implementation decisions

- **`DynamicFieldGrid` / `SectionCard` are defined at module scope**, not
  inside their parent component — this is a deliberate fix for the v1 bug
  where inline component definitions caused focus loss on every keystroke.
- **`SampleExplorer`** is one component reused for the Master Inventory view,
  per-site drill-down, and a Site User's own inventory — passing `siteId`
  (or omitting it for "all accessible sites") rather than three near-
  duplicate pages.
- **RoleGate** is a client-side UX convenience only. Real authorization is
  enforced server-side (FastAPI's `require_roles`); a determined user could
  bypass RoleGate in devtools and would still get a 403 from the API.
- The PDF viewer uses `react-pdf` (pdf.js) against short-lived signed R2
  URLs minted per-request by the backend — nothing is ever publicly
  accessible in the bucket.

## Known gaps / next steps

- Redaction/masking UI (planned, not built — data model is ready on the
  backend via `report_type` / `original_report_id`)
- No automated tests yet
- No CI config
