"""
Alerts API Blueprint
====================

REST endpoints for the alerting subsystem.

Endpoints:
    POST /api/v1/alerts/run           -> Trigger the engine manually (admin only)
    GET  /api/v1/alerts/sla-breached  -> List incidents past their SLA
    GET  /api/v1/alerts/rules         -> Describe active rules (transparency)
"""

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.user import User
from app.services.alerting import AlertEngine, default_rules
from app.services.alerting.engine import get_sla_breached_incidents
from app.api.schemas import incidents_response_schema


alerts_bp = Blueprint("alerts", __name__, url_prefix="/api/v1/alerts")


# ============================================================
# HELPERS
# ============================================================

def _require_admin():
    """Return (None, None) if user is admin, else (error_json, status_code)."""
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    if not user or user.role != "admin":
        return jsonify({
            "error": "Forbidden",
            "message": "This action requires admin privileges.",
            "status_code": 403,
        }), 403
    return None, None


# ============================================================
# RUN ENGINE (admin only)
# ============================================================

@alerts_bp.route("/run", methods=["POST"])
@jwt_required()
def run_engine():
    """Trigger one full alerting evaluation cycle."""
    err, status = _require_admin()
    if err:
        return err, status

    engine = AlertEngine()
    result = engine.run()
    return jsonify({
        "message": "Alert engine cycle completed.",
        "result": result.to_dict(),
    }), 200


# ============================================================
# SLA BREACHED (any authenticated user)
# ============================================================

@alerts_bp.route("/sla-breached", methods=["GET"])
@jwt_required()
def sla_breached():
    """List incidents that have exceeded their SLA timeline."""
    breached = get_sla_breached_incidents()
    return jsonify({
        "count": len(breached),
        "incidents": incidents_response_schema.dump(breached),
    }), 200


# ============================================================
# RULES INTROSPECTION
# ============================================================

@alerts_bp.route("/rules", methods=["GET"])
@jwt_required()
def list_rules():
    """Describe all active alerting rules with their thresholds."""
    rules_info = []
    for rule in default_rules():
        info = {
            "name": rule.name,
            "category": rule.category.value,
            "class": rule.__class__.__name__,
        }
        # Expose thresholds if present
        for attr in ("warning_threshold", "critical_threshold", "error_threshold"):
            if hasattr(rule, attr):
                info[attr] = getattr(rule, attr)
        rules_info.append(info)

    return jsonify({
        "count": len(rules_info),
        "rules": rules_info,
    }), 200