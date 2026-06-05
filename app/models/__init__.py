"""
SQLAlchemy models package.

Importing this module registers all models with SQLAlchemy's metadata,
so that db.create_all() picks them up.
"""

from app.models.user import User
from app.models.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentCategory,
    IncidentSource,
)

__all__ = [
    "User",
    "Incident",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentCategory",
    "IncidentSource",
]