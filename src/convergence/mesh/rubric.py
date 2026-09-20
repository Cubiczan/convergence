"""Row 35 narrative rubric — a real rubric chain over the board narrative.

The Cognitive Mesh Protocol's terminal deliverable is the synthesized
board statement (root cause, why-links, consequences) backed by per-agent
reasoning traces with grounding checks, all recorded in the signed audit
ledger. Those artifacts are gradable, so row 35's rubric-chain pattern is
ADOPTED here: a deterministic, named-criterion rubric evaluates every
synthesized narrative and writes its verdict to the same signed ledger.

Criteria are named and weighted; every failure carries a human-readable
reason. The rubric is deliberately SELF-CONTAINED (no cross-repo
dependency): the chain pattern it adopts is the discipline — named
criteria, explicit weights, evidence on every verdict — not a specific
import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from convergence.mesh.agent import TurnResult

# Mirrors the padding string _synthesize_statement inserts when fewer than
# three real why-links were resolved. Import alongside the synthesizer so
# both compare against ONE constant.
PADDING_WHY_ANSWER = (
    "Because the binding constraint has not been named in shared context."
)

# bridge.build_statement's fallback when a statement is built with no whys.
UNEXPLORED_ROOT_CAUSE = "Root cause not yet explored."

MIN_WHYS = 3

# Single source of truth for criterion weights; must sum to 100 so a fully
# passing narrative scores exactly 100.
CRITERION_WEIGHTS = {
    "root_cause_named": 30,
    "why_links_resolved": 30,
    "grounding_sourced": 25,
    "high_confidence_contribution": 15,
}


@dataclass
class RubricFinding:
    """One criterion's outcome with the evidence for the verdict."""

    criterion: str
    weight: int
    passed: bool
    detail: str


@dataclass
class RubricResult:
    """Aggregated rubric verdict for one synthesized narrative."""

    findings: List[RubricFinding] = field(default_factory=list)
    score: int = 100
    status: str = "CLEAR"

    @property
    def failed(self) -> List[RubricFinding]:
        return [f for f in self.findings if not f.passed]

    def rationale(self) -> str:
        if not self.failed:
            return "All rubric criteria met."
        return "; ".join(f"{f.criterion}: {f.detail}" for f in self.failed)


def evaluate_narrative(*, statement, turns: List[TurnResult]) -> RubricResult:
    """Score a synthesized board statement against the named rubric.

    Deterministic and side-effect free: callers (the orchestrator's audit
    path) append the returned verdict to the signed ledger.
    """
    findings: List[RubricFinding] = []

    root_cause = (statement.root_cause or "").strip()
    root_ok = bool(root_cause) and root_cause not in {
        UNEXPLORED_ROOT_CAUSE,
        PADDING_WHY_ANSWER,
    }
    findings.append(
        RubricFinding(
            criterion="root_cause_named",
            weight=CRITERION_WEIGHTS["root_cause_named"],
            passed=root_ok,
            detail="Root cause must be a named constraint, not the synthesis placeholder.",
        )
    )

    whys = list(statement.whys or [])
    padded = [w for w in whys if (w.answer or "").strip() == PADDING_WHY_ANSWER]
    why_ok = len(whys) >= MIN_WHYS and not padded
    if len(whys) < MIN_WHYS:
        detail = f"only {len(whys)} why-link(s) resolved, need >= {MIN_WHYS}."
    elif padded:
        detail = f"{len(padded)} why-link(s) are placeholder padding, not resolved answers."
    else:
        detail = f"{len(whys)} why-links resolved."
    findings.append(
        RubricFinding(
            criterion="why_links_resolved",
            weight=CRITERION_WEIGHTS["why_links_resolved"],
            passed=why_ok,
            detail=detail,
        )
    )

    groundings = [g for t in turns for g in (t.trace.grounding or [])]
    if not groundings:
        grounding_ok = False
        detail = "no grounding checks were recorded for any contributing turn."
    else:
        unsourced = [
            g.claim for g in groundings if not (g.claim or "").strip() or not (g.source or "").strip()
        ]
        grounding_ok = not unsourced
        detail = (
            f"{len(unsourced)} grounding claim(s) missing a source."
            if unsourced
            else f"all {len(groundings)} grounding claims carry sources."
        )
    findings.append(
        RubricFinding(
            criterion="grounding_sourced",
            weight=CRITERION_WEIGHTS["grounding_sourced"],
            passed=grounding_ok,
            detail=detail,
        )
    )

    high_conf = [t for t in turns if getattr(t.trace.confidence, "value", "") == "high"]
    findings.append(
        RubricFinding(
            criterion="high_confidence_contribution",
            weight=CRITERION_WEIGHTS["high_confidence_contribution"],
            passed=bool(high_conf),
            detail=(
                f"{len(high_conf)} high-confidence turn(s) contributed."
                if high_conf
                else "no contributing turn reached high confidence — narrative rests on unverified reasoning."
            ),
        )
    )

    penalty = sum(f.weight for f in findings if not f.passed)
    score = max(0, 100 - penalty)
    status = "CLEAR" if score == 100 else "REQUIRES_HUMAN_VERIFICATION"
    return RubricResult(findings=findings, score=score, status=status)
