"""Pydantic schema for the dashboard stats endpoint (shared shape across all 3 roles)."""
from typing import Optional

from pydantic import BaseModel


class DashboardStats(BaseModel):
    """
    One shape serves all three dashboards — fields simply aren't populated
    (left as None) when not applicable to the requesting role, rather than
    having three separate response schemas that the frontend has to branch
    on. IT Admin / Inventory Manager get total_sites and total_users;
    Site User gets neither (their own site is implicit).
    """

    total_sites: Optional[int] = None
    total_users: Optional[int] = None
    total_samples: int
    total_reports: int
