"""
Enums shared across ORM models. Kept in one file so role/permission logic
elsewhere (app/api/deps.py) can import a single source of truth instead of
duplicating string literals.
"""
import enum


class UserRole(str, enum.Enum):
    IT_ADMIN = "it_admin"
    INVENTORY_MANAGER = "inventory_manager"
    SITE_USER = "site_user"


class SiteType(str, enum.Enum):
    """
    PARTNER_SITE  — a real hospital/pathology lab that provides specimens.
                     Belongs to itself; its users are SITE_USER role.
    MANAGER_OWNED — an Inventory Manager's personal/independent inventory.
                     Not tied to any external hospital; owned_by_user_id
                     points at the manager who created it. Functionally
                     identical to a partner site for CRUD/permission
                     purposes, just flagged differently for reporting
                     and dashboard grouping.
    """

    PARTNER_SITE = "partner_site"
    MANAGER_OWNED = "manager_owned"


class ReportType(str, enum.Enum):
    ORIGINAL = "original"
    MASKED = "masked"

# NOTE: a SampleType enum (ffpe/frozen_tumor/serum/plasma/whole_blood/other)
# used to live here. It was removed — it didn't match the real Excel
# template, which has "Type of Tissue" (Tumor/NAT) and "Sample Type"
# (e.g. "FFPE Block") as free-text template fields, not a fixed backend
# enum. Both now live in Sample.custom_fields like every other template
# column. See migration 0002_align_with_template.
