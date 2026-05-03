"""Workstream base class and integration brief types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from convergence.chp.models import DecisionCase, Dossier, FoundationAttack, FoundationDisclosure, SessionStatus
from convergence.mesh.agent import MeshAgent, TurnResult
from convergence.mesh.context import ContextEngine


class MappingType(str, Enum):
    CLEAN = "clean"
    JUDGMENT = "judgment"
    POLICY_CONFLICT = "policy_conflict"
    REPORTING_BREAK = "reporting_break"
    NEW_TARGET_REQUIRED = "new_target_required"
    RESTATEMENT_REQUIRED = "restatement_required"


class IssueCategory(str, Enum):
    COA_MAPPING = "CoA mapping"
    KPI_DEFINITION = "KPI definition"
    GROSS_MARGIN = "gross margin / COGS"
    REVENUE_RECOGNITION = "revenue recognition"
    COMMISSIONS = "commissions"
    CAPITALIZED_SOFTWARE = "capitalized software"
    DEFERRED_REVENUE = "deferred revenue"
    CONTRACT_ASSET = "contract asset"
    CLOSE_CALENDAR = "close calendar"
    SYSTEM_DEPENDENCY = "system dependency"
    SYNERGY_COST = "synergy cost"
    SYNERGY_REVENUE = "synergy revenue"


@dataclass
class WorkstreamBrief:
    """Common brief for any integration workstream."""
    title: str
    acquirer: str
    target: str
    day_post_close: int
    owner: str = "cfo"
    high_stakes: bool = True


@dataclass
class MappingLine:
    """A single CoA or reporting mapping line."""
    source_code: str
    source_label: str
    source_description: str
    source_balance: Optional[float] = None
    target_code: str = ""
    target_label: str = ""
    target_description: str = ""
    mapping_type: MappingType = MappingType.CLEAN
    confidence: str = "high"
    issue_category: str = ""
    rationale: str = ""
    controller_review: bool = False
    user_comment: str = ""
    recommended_action: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_code": self.source_code,
            "source_label": self.source_label,
            "source_description": self.source_description,
            "source_balance": self.source_balance,
            "target_code": self.target_code,
            "target_label": self.target_label,
            "target_description": self.target_description,
            "mapping_type": self.mapping_type.value,
            "confidence": self.confidence,
            "issue_category": self.issue_category,
            "rationale": self.rationale,
            "controller_review": self.controller_review,
            "user_comment": self.user_comment,
            "recommended_action": self.recommended_action,
        }


@dataclass
class SynergyItem:
    """A tracked synergy line."""
    category: str
    description: str
    annual_value_usd: float
    status: str = "identified"  # identified | in_progress | realized | at_risk | lost
    probability: float = 0.5
    timeline: str = ""
    owner: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "annual_value_usd": self.annual_value_usd,
            "status": self.status,
            "probability": self.probability,
            "timeline": self.timeline,
            "owner": self.owner,
        }


@dataclass
class WorkstreamStatus:
    """Status snapshot for one workstream."""
    workstream_type: str
    health: str = "green"  # green | amber | red | not_started
    completion_pct: int = 0
    decisions_locked: int = 0
    decisions_open: int = 0
    risks_count: int = 0
    blocked_decisions: int = 0
    next_milestone: str = ""
    next_milestone_date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workstream_type": self.workstream_type,
            "health": self.health,
            "completion_pct": self.completion_pct,
            "decisions_locked": self.decisions_locked,
            "decisions_open": self.decisions_open,
            "risks_count": self.risks_count,
            "blocked_decisions": self.blocked_decisions,
            "next_milestone": self.next_milestone,
            "next_milestone_date": self.next_milestone_date,
        }


class BaseWorkstream(ABC):
    """Abstract base for M&A integration workstreams."""

    def __init__(self, brief: WorkstreamBrief) -> None:
        self.brief = brief
        self.agents: List[MeshAgent] = []
        self.context = ContextEngine()

    @abstractmethod
    def get_agents(self) -> List[MeshAgent]:
        """Return the domain-specific agents for this workstream."""

    @abstractmethod
    def run_analysis(self) -> Dict[str, Any]:
        """Execute the workstream analysis and return structured results."""

    @abstractmethod
    def get_status(self) -> WorkstreamStatus:
        """Return current workstream health status."""
