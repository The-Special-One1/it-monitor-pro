"""
Alerting subsystem.

Exposes:
    AlertEngine    -> Main orchestrator
    Rule           -> Abstract base for custom rules
    default_rules  -> Built-in rule set
"""

from app.services.alerting.engine import AlertEngine, EngineRunResult
from app.services.alerting.rules import (
    Rule, RuleResult, default_rules,
    CpuHighUsageRule, MemoryHighUsageRule,
    DiskHighUsageRule, NetworkErrorsRule,
)

__all__ = [
    "AlertEngine",
    "EngineRunResult",
    "Rule",
    "RuleResult",
    "default_rules",
    "CpuHighUsageRule",
    "MemoryHighUsageRule",
    "DiskHighUsageRule",
    "NetworkErrorsRule",
]