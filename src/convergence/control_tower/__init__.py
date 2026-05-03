"""Control Tower — integration health scoring and steering intelligence."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from convergence.chp.models import IntegrationHealth, SessionStatus
from convergence.workstreams.base import WorkstreamStatus


@dataclass
class RiskItem:
    id: str
    title: str
    category: str
    severity: str = "medium"  # critical | high | medium | low
    status: str = "open"  # open | mitigating | resolved
    owner: str = ""
    impact: str = ""
    mitigation: str = ""
    raised_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "category": self.category,
            "severity": self.severity, "status": self.status, "owner": self.owner,
            "impact": self.impact, "mitigation": self.mitigation, "raised_at": self.raised_at,
        }


@dataclass
class Milestone:
    id: str
    title: str
    target_date: str
    status: str = "pending"  # pending | in_progress | complete | blocked
    workstream: str = ""
    owner: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "target_date": self.target_date,
            "status": self.status, "workstream": self.workstream, "owner": self.owner, "notes": self.notes,
        }


@dataclass
class BlockedDecision:
    id: str
    title: str
    blocking_reason: str
    decision_needed_from: str = ""
    escalated: bool = False
    deadline: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "blocking_reason": self.blocking_reason,
            "decision_needed_from": self.decision_needed_from,
            "escalated": self.escalated, "deadline": self.deadline,
        }


def compute_overall_health(workstream_statuses: List[WorkstreamStatus]) -> IntegrationHealth:
    """Compute overall integration health from workstream statuses."""
    if not workstream_statuses:
        return IntegrationHealth.NOT_STARTED
    weights = {"red": 3, "amber": 2, "green": 1, "not_started": 0}
    max_weight = max(weights.get(ws.health, 0) for ws in workstream_statuses)
    if max_weight >= 3:
        return IntegrationHealth.RED
    if max_weight >= 2:
        return IntegrationHealth.AMBER
    if any(ws.health == "not_started" for ws in workstream_statuses):
        return IntegrationHealth.NOT_STARTED
    return IntegrationHealth.GREEN


def compute_completion_pct(workstream_statuses: List[WorkstreamStatus]) -> int:
    if not workstream_statuses:
        return 0
    return sum(ws.completion_pct for ws in workstream_statuses) // len(workstream_statuses)


class ControlTower:
    """Integration control tower — health, risks, milestones, blocked decisions."""

    def __init__(self, *, acquirer: str = "", target: str = "",
                 day_post_close: int = 0) -> None:
        self.acquirer = acquirer
        self.target = target
        self.day_post_close = day_post_close
        self.workstreams: Dict[str, WorkstreamStatus] = {}
        self.risks: List[RiskItem] = []
        self.milestones: List[Milestone] = []
        self.blocked_decisions: List[BlockedDecision] = []
        self._created_at = time.time()

    def add_workstream(self, status: WorkstreamStatus) -> None:
        self.workstreams[status.workstream_type] = status

    def add_risk(self, risk: RiskItem) -> None:
        self.risks.append(risk)

    def add_milestone(self, milestone: Milestone) -> None:
        self.milestones.append(milestone)

    def add_blocked_decision(self, decision: BlockedDecision) -> None:
        self.blocked_decisions.append(decision)

    @property
    def overall_health(self) -> IntegrationHealth:
        return compute_overall_health(list(self.workstreams.values()))

    @property
    def completion_pct(self) -> int:
        return compute_completion_pct(list(self.workstreams.values()))

    @property
    def critical_risks(self) -> List[RiskItem]:
        return [r for r in self.risks if r.severity in ("critical", "high") and r.status == "open"]

    @property
    def open_milestones(self) -> List[Milestone]:
        return [m for m in self.milestones if m.status != "complete"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "acquirer": self.acquirer,
            "target": self.target,
            "day_post_close": self.day_post_close,
            "overall_health": self.overall_health.value,
            "completion_pct": self.completion_pct,
            "workstreams": {k: v.to_dict() for k, v in self.workstreams.items()},
            "critical_risk_count": len(self.critical_risks),
            "open_milestone_count": len(self.open_milestones),
            "blocked_decision_count": len(self.blocked_decisions),
            "risks": [r.to_dict() for r in self.risks],
            "milestones": [m.to_dict() for m in self.milestones],
            "blocked_decisions": [d.to_dict() for d in self.blocked_decisions],
        }
