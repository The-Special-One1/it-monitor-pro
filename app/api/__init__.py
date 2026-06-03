"""
IT Monitor Pro - Health Check Blueprint
========================================

Health check endpoints used by:
  - Container orchestrators (Docker HEALTHCHECK, Kubernetes liveness/readiness)
  - Load balancers (to remove unhealthy instances from rotation)
  - Monitoring tools (uptime checks, alerting systems)
  - DevOps dashboards

Following industry conventions:
  - /health     → liveness check (is the process alive?)
  - /health/db  → readiness check (can we serve traffic? are dependencies up?)
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify
from sqlalchemy import text

from app.extensions import db


# Create the blueprint
# url_prefix is added when registering in the factory (e.g. /api/v1)
health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """
    Liveness probe — is the application process alive?

    Returns 200 OK if the Flask app is running.
    Should always be fast (no DB queries, no external calls).
    """
    return jsonify({
        "status": "healthy",
        "service": "IT Monitor Pro",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "check": "liveness",
    }), 200


@health_bp.route("/health/db", methods=["GET"])
def health_db():
    """
    Readiness probe — can we serve real traffic?

    Checks if the database is reachable.
    Used by orchestrators to decide whether to send traffic to this instance.

    Returns:
        200 OK if database is reachable
        503 Service Unavailable if database is down
    """
    try:
        # Simple query to verify DB connectivity
        db.session.execute(text("SELECT 1"))
        db_status = "connected"
        status_code = 200
        overall = "healthy"
    except Exception as exc:
        db_status = f"error: {type(exc).__name__}"
        status_code = 503
        overall = "unhealthy"

    return jsonify({
        "status": overall,
        "service": "IT Monitor Pro",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "check": "readiness",
        "dependencies": {
            "database": db_status,
        },
    }), status_code