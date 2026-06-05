"""
Unit tests for the SystemMonitor service.

These tests verify that:
  - Each metric collector returns the expected JSON-serializable shape
  - Threshold classification logic works for all 3 states (OK/WARNING/CRITICAL)
  - All numeric values fall within sane ranges (no negative percentages, etc.)
  - The complete snapshot aggregates all subsystems

We do NOT mock psutil — we run real calls against the test machine.
This is intentional: it guarantees the integration actually works.
"""

import pytest

from app.services.system_monitor import SystemMonitor


# ============================================================
# THRESHOLD CLASSIFICATION (pure logic, no I/O)
# ============================================================

class TestStatusClassification:
    """Tests for the _classify_status helper method."""

    def test_ok_status_below_warning(self):
        assert SystemMonitor._classify_status(10.0, 75.0, 90.0) == "OK"

    def test_ok_status_at_zero(self):
        assert SystemMonitor._classify_status(0.0, 75.0, 90.0) == "OK"

    def test_warning_status_at_threshold(self):
        assert SystemMonitor._classify_status(75.0, 75.0, 90.0) == "WARNING"

    def test_warning_status_between_thresholds(self):
        assert SystemMonitor._classify_status(80.0, 75.0, 90.0) == "WARNING"

    def test_critical_status_at_threshold(self):
        assert SystemMonitor._classify_status(90.0, 75.0, 90.0) == "CRITICAL"

    def test_critical_status_above_threshold(self):
        assert SystemMonitor._classify_status(99.9, 75.0, 90.0) == "CRITICAL"


# ============================================================
# CPU METRICS
# ============================================================

class TestCpuMetrics:
    """Tests for get_cpu_metrics()."""

    def test_returns_dict(self, monitor):
        assert isinstance(monitor.get_cpu_metrics(), dict)

    def test_contains_required_keys(self, monitor):
        data = monitor.get_cpu_metrics()
        required = {
            "usage_percent", "per_core_percent",
            "core_count_logical", "core_count_physical",
            "frequency_mhz", "status", "thresholds",
        }
        assert required.issubset(data.keys())

    def test_usage_percent_in_valid_range(self, monitor):
        data = monitor.get_cpu_metrics()
        assert 0.0 <= data["usage_percent"] <= 100.0

    def test_core_count_is_positive(self, monitor):
        data = monitor.get_cpu_metrics()
        assert data["core_count_logical"] >= 1

    def test_status_is_valid(self, monitor):
        assert monitor.get_cpu_metrics()["status"] in {"OK", "WARNING", "CRITICAL"}


# ============================================================
# MEMORY METRICS
# ============================================================

class TestMemoryMetrics:
    """Tests for get_memory_metrics()."""

    def test_returns_dict(self, monitor):
        assert isinstance(monitor.get_memory_metrics(), dict)

    def test_ram_subsection_present(self, monitor):
        data = monitor.get_memory_metrics()
        assert "ram" in data
        assert {"total_gb", "available_gb", "used_gb", "usage_percent"}.issubset(data["ram"].keys())

    def test_ram_usage_percent_in_range(self, monitor):
        ram = monitor.get_memory_metrics()["ram"]
        assert 0.0 <= ram["usage_percent"] <= 100.0

    def test_ram_total_is_positive(self, monitor):
        ram = monitor.get_memory_metrics()["ram"]
        assert ram["total_gb"] > 0


# ============================================================
# DISK METRICS
# ============================================================

class TestDiskMetrics:
    """Tests for get_disk_metrics()."""

    def test_returns_dict(self, monitor):
        assert isinstance(monitor.get_disk_metrics(), dict)

    def test_at_least_one_partition(self, monitor):
        data = monitor.get_disk_metrics()
        assert len(data["partitions"]) >= 1

    def test_partition_has_required_fields(self, monitor):
        partition = monitor.get_disk_metrics()["partitions"][0]
        required = {"device", "mountpoint", "filesystem", "total_gb", "used_gb", "free_gb", "usage_percent"}
        assert required.issubset(partition.keys())

    def test_worst_usage_in_valid_range(self, monitor):
        data = monitor.get_disk_metrics()
        assert 0.0 <= data["worst_usage_percent"] <= 100.0


# ============================================================
# NETWORK METRICS
# ============================================================

class TestNetworkMetrics:
    """Tests for get_network_metrics()."""

    def test_returns_dict(self, monitor):
        assert isinstance(monitor.get_network_metrics(), dict)

    def test_has_required_counters(self, monitor):
        data = monitor.get_network_metrics()
        required = {"bytes_sent_mb", "bytes_recv_mb", "packets_sent", "packets_recv",
                    "errors_in", "errors_out", "drops_in", "drops_out"}
        assert required.issubset(data.keys())

    def test_counters_are_non_negative(self, monitor):
        data = monitor.get_network_metrics()
        for key in ("bytes_sent_mb", "bytes_recv_mb", "packets_sent", "packets_recv"):
            assert data[key] >= 0


# ============================================================
# COMPLETE SNAPSHOT
# ============================================================

class TestSnapshot:
    """Tests for the aggregated get_snapshot()."""

    def test_snapshot_has_all_subsystems(self, monitor):
        snapshot = monitor.get_snapshot()
        assert {"timestamp", "hostname", "cpu", "memory", "disk", "network"}.issubset(snapshot.keys())

    def test_timestamp_is_iso8601_utc(self, monitor):
        timestamp = monitor.get_snapshot()["timestamp"]
        assert timestamp.endswith("Z")
        assert "T" in timestamp

    def test_hostname_is_non_empty_string(self, monitor):
        hostname = monitor.get_snapshot()["hostname"]
        assert isinstance(hostname, str)
        assert len(hostname) > 0