"""CFO accuracy guard — enforces human verification floor for high-stakes decisions."""
from __future__ import annotations

from convergence.chp.models import DecisionCase, SessionStatus


class AccuracyGuardResult:
    """Result of running the CFO accuracy guard."""

    __slots__ = ("passes", "reason", "required_action")

    def __init__(self, passes: bool, reason: str, required_action: str):
        self.passes = passes
        self.reason = reason
        self.required_action = required_action


def run_accuracy_guard(case: DecisionCase, floor: int = 100) -> AccuracyGuardResult:
    """Check if a decision case meets the accuracy floor for clean lock.

    If the foundation score is below the floor, or structural vulnerabilities
    remain open, the guard forces human verification instead of clean lock.

    Args:
        case: The decision case to evaluate.
        floor: Minimum foundation score for clean lock (default 100 for CFO domain).

    Returns:
        AccuracyGuardResult with pass/fail status and required action.
    """
    score = case.foundation_score or 0
    vulns = case.structural_vulnerabilities or []
    blind = case.blind_spots or []

    issues: list[str] = []

    if score < floor:
        issues.append(f"foundation score {score} below floor {floor}")

    if vulns:
        issues.append(f"{len(vulns)} structural vulnerability(ies) remain open")

    if blind:
        issues.append(f"{len(blind)} blind spot(s) unresolved")

    if issues:
        return AccuracyGuardResult(
            passes=False,
            reason="; ".join(issues),
            required_action="REQUIRES_HUMAN_VERIFICATION",
        )

    # Even if locked, check for violations
    if case.status == SessionStatus.LOCKED and (vulns or blind):
        return AccuracyGuardResult(
            passes=False,
            reason="LOCKED status but vulnerabilities or blind spots detected — downgrade to human review",
            required_action="DOWNGRADE_TO_HUMAN_REVIEW",
        )

    return AccuracyGuardResult(
        passes=True,
        reason="accuracy guard clear",
        required_action="PROCEED",
    )
