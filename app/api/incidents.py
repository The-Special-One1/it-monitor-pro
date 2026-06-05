"""
Incidents API Blueprint
=======================

REST endpoints for IT incident management.
All endpoints require JWT authentication.

Endpoints:
    POST   /api/v1/incidents       -> Create a new incident
    GET    /api/v1/incidents       -> List incidents (filterable, paginated)
    GET    /api/v1/incidents/<id>  -> Get a single incident
    PATCH  /api/v1/incidents/<id>  -> Update fields (assign, change status, etc.)
    DELETE /api/v1/incidents/<id>  -> Soft delete (admin only)
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.extensions import db
from app.models.incident import Incident, IncidentStatus
from app.models.user import User
from app.api.schemas import (
    incident_create_schema,
    incident_update_schema,
    incident_filter_schema,
    incident_response_schema,
    incidents_response_schema,
)


incidents_bp = Blueprint("incidents", __name__, url_prefix="/api/v1/incidents")


# ============================================================
# HELPERS
# ============================================================

def _current_user():
    """Return the User instance for the JWT subject, or None."""
    user_id = get_jwt_identity()
    return db.session.get(User, int(user_id)) if user_id else None


def _require_admin():
    """Return (None, None) if user is admin, else (error_json, status_code)."""
    user = _current_user()
    if not user or user.role != "admin":
        return jsonify({
            "error": "Forbidden",
            "message": "This action requires admin privileges.",
            "status_code": 403,
        }), 403
    return None, None


# ============================================================
# CREATE
# ============================================================

@incidents_bp.route("", methods=["POST"])
@jwt_required()
def create_incident():
    """Create a new incident reported by the current user."""
    try:
        payload = incident_create_schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            "error": "Validation Error",
            "message": "Invalid incident payload.",
            "details": err.messages,
            "status_code": 422,
        }), 422

    user = _current_user()
    if not user:
        return jsonify({"error": "Unauthorized", "status_code": 401}), 401

    incident = Incident(
        title=payload["title"],
        description=payload["description"],
        severity=payload["severity"],
        category=payload["category"],
        source=payload["source"],
        sla_minutes=payload.get("sla_minutes"),
        reported_by_id=user.id,
    )

    # Auto-apply SLA if not provided
    incident.apply_default_sla()

    db.session.add(incident)
    db.session.commit()

    return jsonify({
        "message": "Incident created successfully.",
        "incident": incident_response_schema.dump(incident),
    }), 201


# ============================================================
# LIST (with filters + pagination)
# ============================================================

@incidents_bp.route("", methods=["GET"])
@jwt_required()
def list_incidents():
    """List incidents with optional filters and pagination."""
    try:
        filters = incident_filter_schema.load(request.args)
    except ValidationError as err:
        return jsonify({
            "error": "Validation Error",
            "message": "Invalid query parameters.",
            "details": err.messages,
            "status_code": 422,
        }), 422

    query = Incident.query

    # Soft-delete filter (hidden by default)
    if not filters.get("include_deleted"):
        query = query.filter(Incident.is_deleted.is_(False))

    # Apply filters
    if "status" in filters:
        query = query.filter(Incident.status == filters["status"])
    if "severity" in filters:
        query = query.filter(Incident.severity == filters["severity"])
    if "category" in filters:
        query = query.filter(Incident.category == filters["category"])
    if "source" in filters:
        query = query.filter(Incident.source == filters["source"])
    if "assigned_to_id" in filters:
        query = query.filter(Incident.assigned_to_id == filters["assigned_to_id"])
    if "reported_by_id" in filters:
        query = query.filter(Incident.reported_by_id == filters["reported_by_id"])

    # Order: newest first
    query = query.order_by(Incident.created_at.desc())

    # Paginate
    page = filters["page"]
    per_page = filters["per_page"]
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "incidents": incidents_response_schema.dump(pagination.items),
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }), 200


# ============================================================
# RETRIEVE (single)
# ============================================================

@incidents_bp.route("/<int:incident_id>", methods=["GET"])
@jwt_required()
def get_incident(incident_id):
    """Get a single incident by ID."""
    incident = Incident.query.filter_by(id=incident_id, is_deleted=False).first()
    if not incident:
        return jsonify({
            "error": "Not Found",
            "message": f"Incident {incident_id} does not exist.",
            "status_code": 404,
        }), 404

    return jsonify({"incident": incident_response_schema.dump(incident)}), 200


# ============================================================
# UPDATE (PATCH — partial)
# ============================================================

@incidents_bp.route("/<int:incident_id>", methods=["PATCH"])
@jwt_required()
def update_incident(incident_id):
    """Partially update an incident (assign, change status, etc.)."""
    incident = Incident.query.filter_by(id=incident_id, is_deleted=False).first()
    if not incident:
        return jsonify({
            "error": "Not Found",
            "message": f"Incident {incident_id} does not exist.",
            "status_code": 404,
        }), 404

    try:
        updates = incident_update_schema.load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({
            "error": "Validation Error",
            "message": "Invalid update payload.",
            "details": err.messages,
            "status_code": 422,
        }), 422

    if not updates:
        return jsonify({
            "error": "Bad Request",
            "message": "Provide at least one field to update.",
            "status_code": 400,
        }), 400

    # Apply changes
    for field, value in updates.items():
        if field == "status" and value == IncidentStatus.RESOLVED.value:
            incident.mark_resolved()
        elif field == "assigned_to_id" and value is not None:
            incident.assign_to(value)
        else:
            setattr(incident, field, value)

    db.session.commit()

    return jsonify({
        "message": "Incident updated successfully.",
        "incident": incident_response_schema.dump(incident),
    }), 200


# ============================================================
# SOFT DELETE (admin only)
# ============================================================

@incidents_bp.route("/<int:incident_id>", methods=["DELETE"])
@jwt_required()
def delete_incident(incident_id):
    """Soft-delete an incident (admin only). Audit trail preserved."""
    err_response, status = _require_admin()
    if err_response:
        return err_response, status

    incident = Incident.query.filter_by(id=incident_id, is_deleted=False).first()
    if not incident:
        return jsonify({
            "error": "Not Found",
            "message": f"Incident {incident_id} does not exist.",
            "status_code": 404,
        }), 404

    incident.is_deleted = True
    db.session.commit()

    return jsonify({
        "message": f"Incident {incident_id} soft-deleted successfully.",
        "incident_id": incident_id,
    }), 200