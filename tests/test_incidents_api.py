"""
Integration tests for the Incidents API.

These tests exercise the full HTTP stack:
  Flask -> JWT -> Marshmallow validation -> SQLAlchemy -> SQLite (in-memory)

Each test uses a fresh app + fresh DB (function-scoped fixtures),
guaranteeing perfect isolation between tests.
"""

import pytest

from app.models.incident import (
    Incident, IncidentSeverity, IncidentStatus, IncidentCategory,
)


# ============================================================
# HELPERS
# ============================================================

VALID_PAYLOAD = {
    "title": "Database connection timeout",
    "description": "Production DB taking over 30 seconds to respond.",
    "severity": "HIGH",
    "category": "APPLICATION",
}


def _create_incident(client, headers, **overrides):
    """Helper to POST a new incident and return the response."""
    payload = {**VALID_PAYLOAD, **overrides}
    return client.post("/api/v1/incidents", json=payload, headers=headers)


# ============================================================
# AUTH PROTECTION
# ============================================================

class TestAuthProtection:
    """All incident endpoints must require JWT."""

    def test_post_without_token_returns_401(self, client):
        response = client.post("/api/v1/incidents", json=VALID_PAYLOAD)
        assert response.status_code == 401

    def test_get_list_without_token_returns_401(self, client):
        response = client.get("/api/v1/incidents")
        assert response.status_code == 401

    def test_get_single_without_token_returns_401(self, client):
        response = client.get("/api/v1/incidents/1")
        assert response.status_code == 401

    def test_patch_without_token_returns_401(self, client):
        response = client.patch("/api/v1/incidents/1", json={"status": "CLOSED"})
        assert response.status_code == 401

    def test_delete_without_token_returns_401(self, client):
        response = client.delete("/api/v1/incidents/1")
        assert response.status_code == 401


# ============================================================
# CREATE (POST)
# ============================================================

class TestCreateIncident:

    def test_valid_payload_returns_201(self, client, auth_headers):
        response = _create_incident(client, auth_headers)
        assert response.status_code == 201
        data = response.get_json()
        assert data["message"] == "Incident created successfully."
        assert data["incident"]["title"] == VALID_PAYLOAD["title"]

    def test_auto_applies_sla_for_high_severity(self, client, auth_headers):
        response = _create_incident(client, auth_headers, severity="HIGH")
        assert response.status_code == 201
        # HIGH default SLA = 240 min (4h)
        assert response.get_json()["incident"]["sla_minutes"] == 240

    def test_auto_applies_sla_for_critical_severity(self, client, auth_headers):
        response = _create_incident(client, auth_headers, severity="CRITICAL")
        assert response.status_code == 201
        # CRITICAL default SLA = 60 min (1h)
        assert response.get_json()["incident"]["sla_minutes"] == 60

    def test_defaults_to_open_status(self, client, auth_headers):
        response = _create_incident(client, auth_headers)
        assert response.get_json()["incident"]["status"] == "OPEN"

    def test_defaults_to_manual_source(self, client, auth_headers):
        response = _create_incident(client, auth_headers)
        assert response.get_json()["incident"]["source"] == "MANUAL"

    def test_reported_by_id_taken_from_jwt(self, client, auth_headers, test_user):
        response = _create_incident(client, auth_headers)
        assert response.get_json()["incident"]["reported_by_id"] == test_user.id

    def test_invalid_severity_returns_422(self, client, auth_headers):
        response = _create_incident(client, auth_headers, severity="RAINBOW")
        assert response.status_code == 422
        details = response.get_json()["details"]
        assert "severity" in details

    def test_missing_title_returns_422(self, client, auth_headers):
        payload = {"description": "Some long enough description here."}
        response = client.post("/api/v1/incidents", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_short_title_returns_422(self, client, auth_headers):
        response = _create_incident(client, auth_headers, title="x")
        assert response.status_code == 422


# ============================================================
# LIST (GET) + FILTERS + PAGINATION
# ============================================================

class TestListIncidents:

    def test_empty_list_when_no_incidents(self, client, auth_headers):
        response = client.get("/api/v1/incidents", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["incidents"] == []
        assert data["pagination"]["total"] == 0

    def test_returns_created_incidents(self, client, auth_headers):
        _create_incident(client, auth_headers, severity="LOW")
        _create_incident(client, auth_headers, severity="CRITICAL")
        response = client.get("/api/v1/incidents", headers=auth_headers)
        assert response.get_json()["pagination"]["total"] == 2

    def test_filter_by_severity(self, client, auth_headers):
        _create_incident(client, auth_headers, severity="LOW")
        _create_incident(client, auth_headers, severity="CRITICAL")
        response = client.get(
            "/api/v1/incidents?severity=CRITICAL", headers=auth_headers
        )
        data = response.get_json()
        assert data["pagination"]["total"] == 1
        assert data["incidents"][0]["severity"] == "CRITICAL"

    def test_filter_by_category(self, client, auth_headers):
        _create_incident(client, auth_headers, category="DISK")
        _create_incident(client, auth_headers, category="NETWORK")
        response = client.get(
            "/api/v1/incidents?category=DISK", headers=auth_headers
        )
        assert response.get_json()["pagination"]["total"] == 1

    def test_pagination_per_page(self, client, auth_headers):
        for _ in range(5):
            _create_incident(client, auth_headers)
        response = client.get(
            "/api/v1/incidents?per_page=2&page=1", headers=auth_headers
        )
        data = response.get_json()
        assert len(data["incidents"]) == 2
        assert data["pagination"]["pages"] == 3
        assert data["pagination"]["has_next"] is True

    def test_invalid_filter_returns_422(self, client, auth_headers):
        response = client.get(
            "/api/v1/incidents?severity=BOGUS", headers=auth_headers
        )
        assert response.status_code == 422


# ============================================================
# RETRIEVE (GET single)
# ============================================================

class TestGetIncident:

    def test_returns_existing_incident(self, client, auth_headers):
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]

        response = client.get(
            f"/api/v1/incidents/{incident_id}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.get_json()["incident"]["id"] == incident_id

    def test_returns_404_for_unknown_id(self, client, auth_headers):
        response = client.get("/api/v1/incidents/9999", headers=auth_headers)
        assert response.status_code == 404


# ============================================================
# UPDATE (PATCH)
# ============================================================

class TestUpdateIncident:

    def test_patch_changes_status(self, client, auth_headers):
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]

        response = client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"status": "IN_PROGRESS"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.get_json()["incident"]["status"] == "IN_PROGRESS"

    def test_resolving_sets_resolved_at(self, client, auth_headers):
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]
        assert post_resp.get_json()["incident"]["resolved_at"] is None

        response = client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"status": "RESOLVED"},
            headers=auth_headers,
        )
        data = response.get_json()["incident"]
        assert data["status"] == "RESOLVED"
        assert data["resolved_at"] is not None

    def test_assigning_to_user_moves_to_in_progress(self, client, auth_headers, test_user):
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]

        response = client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={"assigned_to_id": test_user.id},
            headers=auth_headers,
        )
        data = response.get_json()["incident"]
        assert data["assigned_to_id"] == test_user.id
        # assign_to() auto-promotes OPEN -> IN_PROGRESS
        assert data["status"] == "IN_PROGRESS"

    def test_empty_patch_returns_400(self, client, auth_headers):
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]

        response = client.patch(
            f"/api/v1/incidents/{incident_id}",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_patch_404_for_unknown_id(self, client, auth_headers):
        response = client.patch(
            "/api/v1/incidents/9999",
            json={"status": "CLOSED"},
            headers=auth_headers,
        )
        assert response.status_code == 404


# ============================================================
# DELETE (admin only)
# ============================================================

class TestDeleteIncident:

    def test_non_admin_cannot_delete(self, client, auth_headers):
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]

        response = client.delete(
            f"/api/v1/incidents/{incident_id}", headers=auth_headers
        )
        assert response.status_code == 403

    def test_admin_can_soft_delete(self, client, auth_headers, admin_headers):
        # User creates the incident
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]

        # Admin deletes it
        response = client.delete(
            f"/api/v1/incidents/{incident_id}", headers=admin_headers
        )
        assert response.status_code == 200

    def test_soft_deleted_incident_hidden_by_default(
        self, client, auth_headers, admin_headers
    ):
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]

        client.delete(f"/api/v1/incidents/{incident_id}", headers=admin_headers)

        list_resp = client.get("/api/v1/incidents", headers=auth_headers)
        assert list_resp.get_json()["pagination"]["total"] == 0

    def test_include_deleted_filter_shows_soft_deleted(
        self, client, auth_headers, admin_headers
    ):
        post_resp = _create_incident(client, auth_headers)
        incident_id = post_resp.get_json()["incident"]["id"]
        client.delete(f"/api/v1/incidents/{incident_id}", headers=admin_headers)

        list_resp = client.get(
            "/api/v1/incidents?include_deleted=true", headers=auth_headers
        )
        assert list_resp.get_json()["pagination"]["total"] == 1


# ============================================================
# MODEL BUSINESS LOGIC (unit tests, no HTTP)
# ============================================================

class TestIncidentModelLogic:
    """Test Incident model methods directly (no HTTP layer)."""

    def test_apply_default_sla_for_each_severity(self, app, db_session, test_user):
        sla_map = {
            IncidentSeverity.LOW: 4320,
            IncidentSeverity.MEDIUM: 1440,
            IncidentSeverity.HIGH: 240,
            IncidentSeverity.CRITICAL: 60,
        }
        for severity, expected in sla_map.items():
            incident = Incident(
                title="Test incident title",
                description="A description long enough.",
                severity=severity,
                category=IncidentCategory.OTHER,
                reported_by_id=test_user.id,
            )
            incident.apply_default_sla()
            assert incident.sla_minutes == expected, f"Failed for {severity}"

    def test_mark_resolved_sets_timestamp(self, app, db_session, test_user):
        incident = Incident(
            title="To be resolved",
            description="Will be marked resolved.",
            severity=IncidentSeverity.LOW,
            category=IncidentCategory.OTHER,
            reported_by_id=test_user.id,
        )
        assert incident.resolved_at is None
        incident.mark_resolved()
        assert incident.status == IncidentStatus.RESOLVED
        assert incident.resolved_at is not None