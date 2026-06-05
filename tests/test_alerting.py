"""
Tests for the alerting subsystem.

Three layers tested:
  1. Rules (pure logic, no DB)
  2. AlertEngine (DB interactions, idempotency, auto-resolve)
  3. REST API endpoints (HTTP + JWT + RBAC)
"""

import pytest
from unittest.mock import MagicMock

from app.services.system_monitor import SystemMonitor
from app.services.alerting import (
    AlertEngine, CpuHighUsageRule, MemoryHighUsageRule,
    DiskHighUsageRule, NetworkErrorsRule,
)
from app.models.incident import (
    Incident, IncidentSource, IncidentStatus, IncidentSeverity, IncidentCategory,
)


# ============================================================
# FIXTURES specific to alerting tests
# ============================================================

@pytest.fixture
def critical_snapshot():
    """Snapshot that fires CPU, Memory, and Disk rules."""
    return {
        "hostname": "test-host",
        "cpu": {"usage_percent": 96.0},
        "memory": {"ram": {"usage_percent": 97.0, "used_gb": 7.8, "total_gb": 8}},
        "disk": {
            "worst_usage_percent": 93.0,
            "partitions": [{"mountpoint": "/var", "device": "/dev/sda1", "usage_percent": 93.0}],
        },
        "network": {"errors_in": 0, "errors_out": 0, "drops_in": 0, "drops_out": 0},
    }


@pytest.fixture
def healthy_snapshot():
    """Snapshot where no rule fires."""
    return {
        "hostname": "test-host",
        "cpu": {"usage_percent": 10.0},
        "memory": {"ram": {"usage_percent": 30.0, "used_gb": 2, "total_gb": 8}},
        "disk": {"worst_usage_percent": 20.0, "partitions": []},
        "network": {"errors_in": 0, "errors_out": 0, "drops_in": 0, "drops_out": 0},
    }


@pytest.fixture
def mock_monitor(critical_snapshot):
    """SystemMonitor that returns the critical snapshot on demand."""
    monitor = MagicMock(spec=SystemMonitor)
    monitor.get_snapshot.return_value = critical_snapshot
    return monitor


# ============================================================
# 1. RULE TESTS (pure logic)
# ============================================================

class TestRules:

    def test_cpu_rule_fires_critical_above_90(self, critical_snapshot):
        rule = CpuHighUsageRule()
        result = rule.evaluate(critical_snapshot)
        assert result is not None
        assert result.severity == IncidentSeverity.CRITICAL

    def test_cpu_rule_silent_when_healthy(self, healthy_snapshot):
        rule = CpuHighUsageRule()
        assert rule.evaluate(healthy_snapshot) is None

    def test_memory_rule_fires_critical_above_95(self, critical_snapshot):
        rule = MemoryHighUsageRule()
        result = rule.evaluate(critical_snapshot)
        assert result is not None
        assert result.severity == IncidentSeverity.CRITICAL

    def test_disk_rule_fires_critical_above_90(self, critical_snapshot):
        rule = DiskHighUsageRule()
        result = rule.evaluate(critical_snapshot)
        assert result is not None
        assert result.severity == IncidentSeverity.CRITICAL
        assert result.category == IncidentCategory.DISK

    def test_network_rule_silent_when_no_errors(self, healthy_snapshot):
        rule = NetworkErrorsRule()
        assert rule.evaluate(healthy_snapshot) is None

    def test_network_rule_fires_above_threshold(self):
        snapshot = {
            "hostname": "h",
            "network": {"errors_in": 200, "errors_out": 0, "drops_in": 0, "drops_out": 0},
        }
        result = NetworkErrorsRule(error_threshold=100).evaluate(snapshot)
        assert result is not None
        assert result.observed_value == 200.0


# ============================================================
# 2. ALERT ENGINE TESTS (DB interactions)
# ============================================================

class TestAlertEngine:

    def test_run_creates_incidents_for_each_firing_rule(self, app, db_session, mock_monitor):
        engine = AlertEngine(monitor=mock_monitor)
        result = engine.run()
        # Critical snapshot fires CPU, Memory, Disk -> 3 incidents
        assert len(result.created) == 3
        assert len(result.suppressed) == 0

    def test_created_incidents_have_source_automated(self, app, db_session, mock_monitor):
        engine = AlertEngine(monitor=mock_monitor)
        engine.run()
        automated = Incident.query.filter_by(source=IncidentSource.AUTOMATED).all()
        assert len(automated) == 3
        for inc in automated:
            assert inc.source == IncidentSource.AUTOMATED

    def test_idempotency_second_run_creates_nothing(self, app, db_session, mock_monitor):
        engine = AlertEngine(monitor=mock_monitor)
        engine.run()
        result2 = engine.run()
        assert len(result2.created) == 0
        assert len(result2.suppressed) == 3

    def test_auto_resolve_when_condition_clears(
        self, app, db_session, mock_monitor, healthy_snapshot
    ):
        engine = AlertEngine(monitor=mock_monitor)
        engine.run()  # creates 3 incidents

        # System recovers
        mock_monitor.get_snapshot.return_value = healthy_snapshot
        result = engine.run()

        assert len(result.resolved) == 3
        # Confirm they are RESOLVED in DB with timestamp
        resolved = Incident.query.filter_by(status=IncidentStatus.RESOLVED).all()
        assert len(resolved) == 3
        for inc in resolved:
            assert inc.resolved_at is not None

    def test_system_user_created_on_demand(self, app, db_session, mock_monitor):
        from app.models.user import User
        assert User.query.filter_by(email="system@itmonitor.com").first() is None

        engine = AlertEngine(monitor=mock_monitor)
        engine.run()

        system_user = User.query.filter_by(email="system@itmonitor.com").first()
        assert system_user is not None
        assert system_user.is_active is False  # Cannot log in


# ============================================================
# 3. REST API TESTS
# ============================================================

class TestAlertsAPI:

    def test_rules_endpoint_requires_auth(self, client):
        response = client.get("/api/v1/alerts/rules")
        assert response.status_code == 401

    def test_rules_endpoint_returns_all_rules(self, client, auth_headers):
        response = client.get("/api/v1/alerts/rules", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 4
        rule_names = {r["name"] for r in data["rules"]}
        assert rule_names == {
            "cpu_high_usage", "memory_high_usage",
            "disk_high_usage", "network_errors",
        }

    def test_run_endpoint_forbidden_for_non_admin(self, client, auth_headers):
        response = client.post("/api/v1/alerts/run", headers=auth_headers)
        assert response.status_code == 403

    def test_run_endpoint_works_for_admin(self, client, admin_headers):
        response = client.post("/api/v1/alerts/run", headers=admin_headers)
        assert response.status_code == 200
        body = response.get_json()
        assert "result" in body
        assert "summary" in body["result"]

    def test_sla_breached_endpoint_returns_list(self, client, auth_headers):
        response = client.get("/api/v1/alerts/sla-breached", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "count" in data
        assert "incidents" in data
        assert isinstance(data["incidents"], list)