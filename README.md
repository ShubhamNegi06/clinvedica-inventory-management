# Clinvedica Specimen Inventory — v2 (Production Rebuild)

Fresh backend + frontend build, reusing the existing Supabase database,
Supabase Auth project, and Cloudflare R2 bucket from v1. See
`backend/README.md` and `frontend/README.md` for setup instructions specific
to each half.

## Quick start order

1. **Backend first** — get `uv sync`, `.env`, `alembic upgrade head` (against
   staging), and `uvicorn` running. Confirm `/docs` loads and `/health`
   returns OK.
2. **Seed field definitions** — edit `backend/scripts/seed_field_definitions.py`
   to match your real Excel template columns, then run it.
3. **Create your first IT Admin user directly in the database** (or via a
   one-off script) — the `POST /users` endpoint itself requires an existing
   IT Admin/Inventory Manager to call it, so the very first account needs to
   be seeded manually.
4. **Frontend** — `npm install`, `.env.local`, `npm run dev`. Log in as the
   IT Admin you just seeded.

## What was verified in this build environment

- Backend: all models build correctly (verified via SQLAlchemy metadata
  dump), all 17 API routes register and are reachable via `TestClient`,
  Alembic migration is syntax-checked and hand-verified column-for-column
  against the model metadata.
- Frontend: `tsc --noEmit` passes clean, `next build` succeeds for all 12
  routes.

## What was NOT verified (no network path to your infrastructure)

- The Alembic migration has not been run against a real Postgres database.
- No route has been tested against a real Supabase Auth token or a real R2
  bucket.
- The full login → dashboard → create sample → upload report flow has not
  been exercised end-to-end.

**Recommended before production:** stand up a staging Supabase branch (or a
throwaway project), point both `.env` files at it, and walk through every
role's flow manually before pointing this at your real database.

## Feature checklist against the original spec

| Feature | Status |
|---|---|
| IT Admin: inventories, samples, users/sites, reports | ✅ built |
| Inventory Manager: inventories (incl. master), own inventory, samples, reports, sites | ✅ built |
| Site User: own inventory CRUD (samples + reports) | ✅ built |
| Bulk ingestion (Excel) | ✅ built, per-row error reporting |
| Subject-ID autofill | ✅ built |
| Autofill suggestions while typing | ✅ built |
| Tag filtering | ✅ built |
| Export to Excel | ✅ built |
| PDF viewer | ✅ built (react-pdf + signed R2 URLs) |
| Dashboards (role-scoped stat cards) | ✅ built |
| Create Users (role picker) | ✅ built |
| Create Sites (incl. manager-owned) | ✅ built |
| Redaction/masking workflow | ⏳ data model ready, UI/backend not built |
| Automated tests | ⏳ not built |
| Docker/deployment config | ⏳ not built |
