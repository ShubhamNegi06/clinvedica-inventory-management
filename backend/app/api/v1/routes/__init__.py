"""
Aggregates all v1 route modules under one router, included once in
app/main.py. New route modules (reports, bulk-ingest, export, field
definitions) get added here as Phase 2 lands.
"""
from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    bulk_ingest,
    dashboard,
    export,
    field_definitions,
    reports,
    samples,
    sites,
    subjects,
    users,
)

router = APIRouter()
router.include_router(auth.router)
router.include_router(sites.router)
router.include_router(users.router)
# IMPORTANT: bulk_ingest and export must be registered BEFORE samples.router.
# Starlette matches routes in registration order, and both
# "/samples/export" and "/samples/bulk-ingest/{site_id}" would otherwise
# be swallowed by samples.router's "/samples/{sample_id}" path.
router.include_router(bulk_ingest.router)
router.include_router(export.router)
router.include_router(samples.router)
router.include_router(reports.router)
router.include_router(subjects.router)
router.include_router(field_definitions.router)
router.include_router(dashboard.router)
