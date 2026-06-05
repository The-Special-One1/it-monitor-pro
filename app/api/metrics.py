"""
Metrics API Blueprint
=====================

REST endpoints for system monitoring metrics.
All endpoints require JWT authentication.

Endpoints:
    GET /api/v1/metrics/health   -> Aggregated health status (OK/WARNING/CRITICAL)
    GET /api/v1/metrics/system   -> Full snapshot (CPU + memory + disk + network)
    GET /api/v1/metrics/cpu      -> CPU only
    GET /api/v1/metrics/memory   -> Memory only
    GET /api/v1/metrics/disk     -> Disk only
    GET /api/v1/metrics/network  -> Network only
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.system_monitor import SystemMonitor


# Blueprint with URL prefix /api/v1/metrics
metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/v1/metrics")

# Single instance reused across requests (stateless, thread-safe)
_monitor = SystemMonitor()


# ============================================================
# HEALTH SUMMARY
# ============================================================

@metrics_bp.route("/health", methods=["GET"])
@jwt_required()
def metrics_health():
    """
    Aggregated health status across all subsystems.

    Returns the worst status (OK < WARNING < CRITICAL) so that
    a single field can drive dashboards and alerting rules.
    """
    cpu = _monitor.get_cpu_metrics()
    memory = _monitor.get_memory_metrics()
    disk = _monitor.get_disk_metrics()

    # Worst status wins
    severity_order = {"OK": 0, "WARNING": 1, "CRITICAL": 2}
    worst = max(
        [cpu["status"], memory["status"], disk["status"]],
        key=lambda s: severity_order[s],
    )

    return jsonify({
        "overall_status": worst,
        "subsystems": {
            "cpu": cpu["status"],
            "memory": memory["status"],
            "disk": disk["status"],
        },
        "requested_by": get_jwt_identity(),
    }), 200


# ============================================================
# FULL SNAPSHOT
# ============================================================

@metrics_bp.route("/system", methods=["GET"])
@jwt_required()
def metrics_system():
    """Return a complete snapshot of all system metrics."""
    return jsonify(_monitor.get_snapshot()), 200


# ============================================================
# INDIVIDUAL METRICS
# ============================================================

@metrics_bp.route("/cpu", methods=["GET"])
@jwt_required()
def metrics_cpu():
    """Return CPU metrics only."""
    return jsonify(_monitor.get_cpu_metrics()), 200


@metrics_bp.route("/memory", methods=["GET"])
@jwt_required()
def metrics_memory():
    """Return memory (RAM + swap) metrics only."""
    return jsonify(_monitor.get_memory_metrics()), 200


@metrics_bp.route("/disk", methods=["GET"])
@jwt_required()
def metrics_disk():
    """Return disk usage metrics only."""
    return jsonify(_monitor.get_disk_metrics()), 200


@metrics_bp.route("/network", methods=["GET"])
@jwt_required()
def metrics_network():
    """Return network I/O metrics only."""
    return jsonify(_monitor.get_network_metrics()), 200