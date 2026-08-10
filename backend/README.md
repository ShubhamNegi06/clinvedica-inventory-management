# Specimen Inventory — Backend (v2)

FastAPI + SQLAlchemy backend for the Clinvedica Specimen Inventory platform.
Reuses your existing Supabase Postgres database, Supabase Auth project, and
Cloudflare R2 bucket — this is a fresh application layer, not a new database.

## Setup

```powershell
# 1. Install dependencies (uv)
uv sync

# 2. Configure environment
copy .env.example .env
# then fill in DATABASE_URL, SUPABASE_*, R2_* with your real values

# 3. Run migrations against a STAGING database first
uv run alembic upgrade head

# 4. Seed standard field definitions (edit scripts/seed_field_definitions.py
#    to match your real Excel template columns before running against prod)
uv run python scripts/seed_field_definitions.py

# 5. Start the dev server
uv run uvicorn app.main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

## Important notes before going to production

- **The Alembic migration (`alembic/versions/0001_initial_schema.py`) was
  hand-written and has NOT been run against a live database** — this sandbox
  had no network path to Supabase. Run it against a staging/branch database
  first and inspect the resulting schema before touching production.
- `SUPABASE_SERVICE_ROLE_KEY` is required for user provisioning (`POST
  /users`) — it calls the Supabase Admin API to create auth accounts. Keep
  this key server-side only, never expose it to the frontend.
- CORS origins are controlled by `CORS_ORIGINS` in `.env` (comma-separated).
  Add your production frontend domain before deploying.
- The known v1 bug (reports orphaned in R2 on sample delete) is fixed
  structurally here: `sample_service.soft_delete_sample` always calls
  `report_service.purge_reports_for_sample` in the same transaction — there
  is no code path that skips it.

## Project layout

```
app/
  core/       # config, security (Supabase JWT verification), exceptions
  db/         # SQLAlchemy engine/session
  models/     # ORM models (User, Site, Sample, Report, FieldDefinition)
  schemas/    # Pydantic request/response models
  api/        # FastAPI routes + RBAC dependencies (api/deps.py)
  services/   # business logic, one module per resource
alembic/      # migrations
scripts/      # one-off/maintenance scripts (field definition seeding)
```

## Role model

- **IT Admin** / **Inventory Manager** — see and manage every site/sample/
  report/user across the system. "Master Inventory" is not a table; it's
  simply an unfiltered query (`site_id` omitted) across all sites.
- **Site User** — scoped to exactly one site (`users.site_id`). Every list/
  get query is filtered at the query level via `get_accessible_site_ids` in
  `app/api/deps.py`, not just gated at the route level.
- An Inventory Manager's "own inventory" is a `Site` row with
  `site_type=manager_owned` — structurally identical to a partner site.
