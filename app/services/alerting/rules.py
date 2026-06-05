"""
Alert Rules
===========

Each Rule evaluates a SystemMonitor snapshot and decides whether
an incident should be raised.

Design pattern: Strategy
  - Each rule is an independent class with .evaluate() method
  - The RuleEngine iterates over rules polymorphically
  - Adding a new rule = new class, no changes to existing code

Each rule returns either None (no incident) or a RuleResult dataclass
describing the incident to be created.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any

from app.models.incident import IncidentSeverity, IncidentCategory


# ============================================================
# RULE RESULT (immutable data class)
# ============================================================

@dataclass(frozen=True)
class RuleResult:
    """
    Result of a rule evaluation that triggered an alert.

    Immutable (frozen=True) because rule results should not be mutated
    after creation — they represent a point-in-time observation.
    """
    rule_name: str
    severity: IncidentSeverity
    category: IncidentCategory
    title: str
    description: str
    observed_value: float
    threshold: float

    def to_incident_dict(self, reported_by_id: int) -> Dict[str, Any]:
        """Convert this result into kwargs ready for Incident()."""
        from app.models.incident import IncidentSource
        return {
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "source": IncidentSource.AUTOMATED,
            "reported_by_id": reported_by_id,
        }


# ============================================================
# BASE RULE (abstract)
# ============================================================

class Rule(ABC):
    """
    Abstract base class for all alert rules.

    Subclasses must implement evaluate() to inspect the snapshot
    and return either None (healthy) or a RuleResult (incident raised).
    """

    # Subclasses must set these
    name: str = ""
    category: IncidentCategory = IncidentCategory.OTHER

    @abstractmethod
    def evaluate(self, snapshot: Dict[str, Any]) -> Optional[RuleResult]:
        """
        Inspect a SystemMonitor snapshot and decide if an alert fires.

        Args:
            snapshot: Output of SystemMonitor.get_snapshot().

        Returns:
            None if the system is healthy under this rule.
            A RuleResult if an alert should be raised.
        """
        raise NotImplementedError


# ============================================================
# CPU RULE
# ============================================================

class CpuHighUsageRule(Rule):
    """
    Fire an alert when CPU usage exceeds the threshold.

    Severity escalates with usage:
        >= warning_threshold (default 75%)  -> HIGH
        >= critical_threshold (default 90%) -> CRITICAL
    """

    name = "cpu_high_usage"
    category = IncidentCategory.CPU

    def __init__(
        self,
        warning_threshold: float = 75.0,
        critical_threshold: float = 90.0,
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def evaluate(self, snapshot: Dict[str, Any]) -> Optional[RuleResult]:
        cpu = snapshot.get("cpu", {})
        usage = cpu.get("usage_percent", 0.0)

        if usage >= self.critical_threshold:
            severity = IncidentSeverity.CRITICAL
            threshold = self.critical_threshold
        elif usage >= self.warning_threshold:
            severity = IncidentSeverity.HIGH
            threshold = self.warning_threshold
        else:
            return None  # Healthy

        return RuleResult(
            rule_name=self.name,
            severity=severity,
            category=self.category,
            title=f"CPU usage {severity.value.lower()}: {usage:.1f}%",
            description=(
                f"CPU usage reached {usage:.1f}% on host "
                f"{snapshot.get('hostname', 'unknown')}, "
                f"exceeding the {threshold}% threshold. "
                f"Check for runaway processes."
            ),
            observed_value=usage,
            threshold=threshold,
        )


# ============================================================
# MEMORY RULE
# ============================================================

class MemoryHighUsageRule(Rule):
    """Fire alert when RAM usage exceeds threshold."""

    name = "memory_high_usage"
    category = IncidentCategory.MEMORY

    def __init__(
        self,
        warning_threshold: float = 80.0,
        critical_threshold: float = 95.0,
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def evaluate(self, snapshot: Dict[str, Any]) -> Optional[RuleResult]:
        ram = snapshot.get("memory", {}).get("ram", {})
        usage = ram.get("usage_percent", 0.0)

        if usage >= self.critical_threshold:
            severity = IncidentSeverity.CRITICAL
            threshold = self.critical_threshold
        elif usage >= self.warning_threshold:
            severity = IncidentSeverity.HIGH
            threshold = self.warning_threshold
        else:
            return None

        return RuleResult(
            rule_name=self.name,
            severity=severity,
            category=self.category,
            title=f"Memory usage {severity.value.lower()}: {usage:.1f}%",
            description=(
                f"RAM usage at {usage:.1f}% (used {ram.get('used_gb', 0)}GB "
                f"of {ram.get('total_gb', 0)}GB) on host "
                f"{snapshot.get('hostname', 'unknown')}, exceeding {threshold}%. "
                f"Investigate memory leaks or scale up resources."
            ),
            observed_value=usage,
            threshold=threshold,
        )


# ============================================================
# DISK RULE
# ============================================================

class DiskHighUsageRule(Rule):
    """Fire alert when ANY disk partition exceeds threshold."""

    name = "disk_high_usage"
    category = IncidentCategory.DISK

    def __init__(
        self,
        warning_threshold: float = 80.0,
        critical_threshold: float = 90.0,
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def evaluate(self, snapshot: Dict[str, Any]) -> Optional[RuleResult]:
        disk = snapshot.get("disk", {})
        worst = disk.get("worst_usage_percent", 0.0)

        if worst >= self.critical_threshold:
            severity = IncidentSeverity.CRITICAL
            threshold = self.critical_threshold
        elif worst >= self.warning_threshold:
            severity = IncidentSeverity.HIGH
            threshold = self.warning_threshold
        else:
            return None

        # Identify the worst partition for the description
        worst_partition = max(
            disk.get("partitions", []),
            key=lambda p: p.get("usage_percent", 0),
            default={},
        )

        return RuleResult(
            rule_name=self.name,
            severity=severity,
            category=self.category,
            title=f"Disk usage {severity.value.lower()}: {worst:.1f}%",
            description=(
                f"Partition {worst_partition.get('mountpoint', '?')} "
                f"({worst_partition.get('device', '?')}) at {worst:.1f}% "
                f"on host {snapshot.get('hostname', 'unknown')}, "
                f"exceeding {threshold}%. Free up space or extend the volume."
            ),
            observed_value=worst,
            threshold=threshold,
        )


# ============================================================
# NETWORK RULE
# ============================================================

class NetworkErrorsRule(Rule):
    """Fire alert when network errors or drops exceed threshold."""

    name = "network_errors"
    category = IncidentCategory.NETWORK

    def __init__(self, error_threshold: int = 100):
        self.error_threshold = error_threshold

    def evaluate(self, snapshot: Dict[str, Any]) -> Optional[RuleResult]:
        net = snapshot.get("network", {})
        total_errors = (
            net.get("errors_in", 0) + net.get("errors_out", 0)
            + net.get("drops_in", 0) + net.get("drops_out", 0)
        )

        if total_errors < self.error_threshold:
            return None

        # Severity based on magnitude
        if total_errors >= self.error_threshold * 10:
            severity = IncidentSeverity.CRITICAL
        else:
            severity = IncidentSeverity.HIGH

        return RuleResult(
            rule_name=self.name,
            severity=severity,
            category=self.category,
            title=f"Network errors elevated: {total_errors} total events",
            description=(
                f"Detected {total_errors} network errors/drops "
                f"({net.get('errors_in', 0)} err_in, "
                f"{net.get('errors_out', 0)} err_out, "
                f"{net.get('drops_in', 0)} drop_in, "
                f"{net.get('drops_out', 0)} drop_out) "
                f"on host {snapshot.get('hostname', 'unknown')}. "
                f"Check cabling, NIC drivers and switch ports."
            ),
            observed_value=float(total_errors),
            threshold=float(self.error_threshold),
        )


# ============================================================
# DEFAULT RULE SET
# ============================================================

def default_rules() -> list:
    """
    Build the default set of rules used by the alerting engine.

    Centralized factory — change defaults in one place.
    """
    return [
        CpuHighUsageRule(),
        MemoryHighUsageRule(),
        DiskHighUsageRule(),
        NetworkErrorsRule(),
    ]