"""
Frontend consumer contract - proposed additive extensions to rfc/models.py.

This does NOT modify models.py. It subclasses the shared dataclasses and adds
the fields the frontend needs (task <-> IOM mapping, canary deployment/trigger
state, canary event log). Every new field has a default, so these are
drop-in replacements for the base classes - existing code that only knows
about the base classes keeps working.

Once backend agrees on the shape, these fields should move into models.py
proper and this file goes away.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from rfc.models import CanaryInstance as _BaseCanaryInstance
from rfc.models import Task as _BaseTask


# --- Enums -------------------------------------------------------------
# String enums so values serialize as plain strings over the wire (JSON,
# dataclasses.asdict, etc.) without a custom encoder.

class ComplianceStatus(str, Enum):
    """Overall audit outcome for a Company, derived from its canaries'
    trigger state (NOT a certification label like "SOC2 compliant").
    Proposed for Company.compliance_status."""
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    NON_COMPLIANT = "non_compliant"
    PENDING_REVIEW = "pending_review"


class DeploymentHealth(str, Enum):
    """Operational health of a CanaryInstance's deployment, independent
    of whether it has been triggered."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    PENDING = "pending"


class LogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    TRIGGER = "trigger"


@dataclass
class Task(_BaseTask):
    # Which IOMs this task has been mapped to (the audit's compliance
    # mapping step). Drives the mind-map view's branches.
    iom_ids: list[str] = field(default_factory=list)


@dataclass
class CanaryInstance(_BaseCanaryInstance):
    # Which task this instance is deployed against.
    task_id: str = field(default_factory=str)
    # IOMs this specific instance covers detection for (subset of the
    # task's iom_ids, and consistent with IOM.linked_canary_type_ids for
    # this instance's canary_type_id).
    iom_ids: list[str] = field(default_factory=list)
    deployment_health: str = DeploymentHealth.PENDING.value
    triggered: bool = False
    # Set only when triggered=True; must be one of iom_ids.
    triggered_iom_id: Optional[str] = None
    deployed_at: Optional[str] = None  # ISO 8601
    last_heartbeat_at: Optional[str] = None  # ISO 8601
    target_url: Optional[str] = None  # where the canary is deployed, if applicable


@dataclass
class CanaryEvent:
    """A single log/log-like entry from a CanaryInstance's monitoring
    stream. TRIGGER-level events are what promote a canary to
    triggered=True and surface an IOM detection."""
    id: str
    canary_instance_id: str
    timestamp: str  # ISO 8601
    level: str  # LogLevel
    message: str
    iom_id: Optional[str] = None  # set when level == LogLevel.TRIGGER
