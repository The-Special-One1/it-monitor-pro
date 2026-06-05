"""
Alert Engine
============

Orchestrates:
  1. Take a snapshot from SystemMonitor
  2. Evaluate all rules against the snapshot
  3. Create new automated Incidents (with idempotency)
  4. Auto-resolve previously-open incidents when condition clears

Idempotency strategy:
  Before creating an incident, look up any open AUTOMATED incident
  for the same (category) — if one exists, skip creation but optionally
  update the description with the latest observed value.

Auto-resolve:
  After evaluating all rules, any open AUTOMATED incident whose
  category did NOT fire is marked RESOLVED.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from app.extensions import db
from app.models.incident import (
    Incident, IncidentStatus, IncidentSource, IncidentCategory,
)
from app.models.user import User
from app.services.system_monitor import SystemMonitor
from app.services.alerting.rules import Rule, RuleResult, default_rules


# ============================================================
# RESULT DATA CLASS
# ============================================================

class EngineRunResult:
    """Summary of a single engine run, useful for logging / API responses."""

    def __init__(self):
        self.created: List[int] = []        # Incident IDs newly created
        self.suppressed: List[str] = []     # Rule names skipped (idempotency)
        self.resolved: List[int] = []       # Incident IDs auto-resolved
        self.timestamp: str = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "created_incidents": self.created,
            "suppressed_rules": self.suppressed,
            "auto_resolved_incidents": self.resolved,
            "summary": {
                "created_count": len(self.created),
                "suppressed_count": len(self.suppressed),
                "resolved_count": len(self.resolved),
            },
        }


# ============================================================
# ALERT ENGINE
# ============================================================

class AlertEngine:
    """
    Evaluates monitoring snapshots and produces incidents.

    Stateless between runs — all state lives in the database.
    Thread-safe to be called from a scheduler.
    """

    def __init__(
        self,
        monitor: Optional[SystemMonitor] = None,
        rules: Optional[List[Rule]] = None,
        system_user_email: str = "system@itmonitor.com",
    ):
        self._monitor = monitor or SystemMonitor()
        self._rules = rules or default_rules()
        self._system_user_email = system_user_email

    # ------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------

    def run(self) -> EngineRunResult:
        """
        Execute one full evaluation cycle.

        Steps:
          1. Snapshot current metrics
          2. For each rule that fires: create or suppress an incident
          3. Auto-resolve incidents whose conditions cleared
        """
        result = EngineRunResult()
        snapshot = self._monitor.get_snapshot()
        system_user = self._get_or_create_system_user()

        firing_categories: set = set()

        # --- Step 2: evaluate rules ---
        for rule in self._rules:
            rule_result = rule.evaluate(snapshot)
            if rule_result is None:
                continue

            firing_categories.add(rule_result.category)

            existing = self._find_open_automated_incident(rule_result.category)
            if existing:
                result.suppressed.append(rule.name)
                # Optionally refresh the description with the latest value
                existing.description = rule_result.description
            else:
                incident = self._create_incident(rule_result, system_user.id)
                result.created.append(incident.id)

        # --- Step 3: auto-resolve cleared incidents ---
        result.resolved = self._auto_resolve_cleared(firing_categories)

        db.session.commit()
        return result

    # ------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------

    def _get_or_create_system_user(self) -> User:
        """
        Ensure a 'system' user exists to own AUTOMATED incidents.
        We need a real user_id because reported_by_id is NOT NULL.
        """
        user = User.query.filter_by(email=self._system_user_email).first()
        if user:
            return user

        # Create on the fly with a long random password (never used to login)
        import secrets
        from app.utils.security import hash_password
        user = User(
            email=self._system_user_email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name="Alert Engine (System)",
            role="admin",
            is_active=False,  # Cannot log in
        )
        db.session.add(user)
        db.session.flush()  # Get the ID without committing yet
        return user

    def _find_open_automated_incident(
        self, category: IncidentCategory
    ) -> Optional[Incident]:
        """
        Look up any open AUTOMATED incident for the given category.

        We consider OPEN or IN_PROGRESS as 'active'.
        """
        return Incident.query.filter(
            Incident.category == category,
            Incident.source == IncidentSource.AUTOMATED,
            Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS]),
            Incident.is_deleted.is_(False),
        ).first()

    def _create_incident(
        self, rule_result: RuleResult, system_user_id: int
    ) -> Incident:
        """Create a new AUTOMATED incident from a rule result."""
        incident = Incident(**rule_result.to_incident_dict(system_user_id))
        incident.apply_default_sla()
        db.session.add(incident)
        db.session.flush()  # Get the ID before commit
        return incident

    def _auto_resolve_cleared(
        self, firing_categories: set
    ) -> List[int]:
        """
        Auto-resolve any open AUTOMATED incident whose category did NOT fire.

        Returns list of resolved incident IDs.
        """
        all_categories = {rule.category for rule in self._rules}
        cleared_categories = all_categories - firing_categories

        if not cleared_categories:
            return []

        open_incidents = Incident.query.filter(
            Incident.category.in_(cleared_categories),
            Incident.source == IncidentSource.AUTOMATED,
            Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS]),
            Incident.is_deleted.is_(False),
        ).all()

        resolved_ids = []
        for incident in open_incidents:
            incident.mark_resolved()
            resolved_ids.append(incident.id)
        return resolved_ids

        

# ============================================================
# SLA QUERY HELPERS
# ============================================================

def get_sla_breached_incidents() -> List[Incident]:
    """
    Return all open incidents that have exceeded their SLA.

    Used by:
      - Dashboard "in breach" widget
      - GET /api/v1/alerts/sla-breached endpoint
      - Future email/Slack notifier
    """
    open_incidents = Incident.query.filter(
        Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS]),
        Incident.is_deleted.is_(False),
        Incident.sla_minutes.isnot(None),
    ).all()

    # SLA breach calculation is done in Python via is_sla_breached()
    # so we can't filter at SQL level — but the open set is usually small.
    return [inc for inc in open_incidents if inc.is_sla_breached()]