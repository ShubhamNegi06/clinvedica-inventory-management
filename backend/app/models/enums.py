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


class SampleType(str, enum.Enum):
    FFPE = "ffpe"
    FROZEN_TUMOR = "frozen_tumor"
    SERUM = "serum"
    PLASMA = "plasma"
    WHOLE_BLOOD = "whole_blood"
    OTHER = "other"
