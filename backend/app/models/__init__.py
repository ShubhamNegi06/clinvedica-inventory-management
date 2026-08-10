"""
Import every model here so:
  1. Alembic's `target_metadata = Base.metadata` picks up all tables for
     autogenerate.
  2. Relationship string references (e.g. Mapped["Site"]) resolve at
     mapper-configuration time regardless of import order elsewhere.
"""
from app.models.field_definition import FieldDefinition  # noqa: F401
from app.models.report import Report  # noqa: F401
from app.models.sample import Sample  # noqa: F401
from app.models.site import Site  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = ["User", "Site", "Sample", "Report", "FieldDefinition"]
