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
        if unsourced:
            # Grounding was ATTEMPTED but incomplete — same 25-point penalty
            # as no grounding at all, but the message distinguishes the two
            # so a human reviewer knows which remediation applies.
            detail = (
                f"grounding attempted, claim lacks source: "
                f"{len(unsourced)} claim(s) without a source."
            )
        else:
            detail = f"all {len(groundings)} grounding claims carry sources."
    findings.append(
        RubricFinding(
            criterion="grounding_sourced",
            weight=CRITERION_WEIGHTS["grounding_sourced"],
            passed=grounding_ok,
            detail=detail,
        )
    )

    high_conf = [t for t in turns if getattr(t.trace.confidence, "value", "") == "high"]
    # Name WHY the confidence never reached high: a populated
    # what_would_change is the agents' own record of principled uncertainty
    # ("the question is hard"); its absence means the analysis itself is
    # incomplete — nothing was articulated that would change the conclusion.
    principled = [t for t in turns if (getattr(t.trace, "what_would_change", "") or "").strip()]
    if high_conf:
        conf_detail = f"{len(high_conf)} high-confidence turn(s) contributed."
    elif principled:
        conf_detail = (
            f"no contributing turn reached high confidence — the question is hard: "
            f"{len(principled)} turn(s) explicitly name what would change their mind."
        )
    else:
        conf_detail = (
            "analysis incomplete: no turn reached high confidence and no turn names "
            "what would change its mind (what_would_change empty on every turn)."
        )
    findings.append(
        RubricFinding(
            criterion="high_confidence_contribution",
            weight=CRITERION_WEIGHTS["high_confidence_contribution"],
            passed=bool(high_conf),
            detail=conf_detail,
        )
    )

    penalty = sum(f.weight for f in findings if not f.passed)
    score = max(0, 100 - penalty)
    status = "CLEAR" if score == 100 else "REQUIRES_HUMAN_VERIFICATION"
    return RubricResult(findings=findings, score=score, status=status)


# ─── Lock-promotion enforcement ────────────────────────────────────────────
#
# The rubric's REQUIRES_HUMAN_VERIFICATION verdict means the same thing the
# CHP state machine's identically-named status means: promotion is blocked
# until a named human acknowledges (four-eyes) or the narrative is
# regenerated and re-graded to CLEAR. One label, one consequence, anywhere
# in the signed ledger.


@dataclass
class RubricClearance:
    """The governing rubric state for one problem, as scanned from the ledger."""

    enforced: bool
    status: str | None
    reason: str

    @property
    def promotable(self) -> bool:
        return not self.enforced


def clearance_for_problem(records: list, problem: str) -> RubricClearance:
    """Scan signed-ledger records for the governing rubric verdict on `problem`.

    The join key is the narrative's problem statement — the same string the
    orchestrator passed to orchestrate() and recorded in the
    narrative_rubric event's inputs. The LATEST narrative_rubric event for
    the problem wins; a REQUIRES_HUMAN_VERIFICATION verdict is cleared only
    by a LATER narrative_rubric_ack event naming a human (confirmed_by,
    non-empty) — the four-eyes pattern, never machine-authorable.
    """
    verdicts = [
        r for r in records
        if r.get("event") == "narrative_rubric"
        and r.get("inputs", {}).get("problem") == problem
    ]
    if not verdicts:
        # No narrative was graded for this problem: the rubric enforces
        # nothing here (CHP-only flows run without ceremony).
        return RubricClearance(enforced=False, status=None,
                               reason="no narrative_rubric verdict recorded for this problem")
    latest = verdicts[-1]
    status = latest.get("inputs", {}).get("status")
    if status == "CLEAR":
        return RubricClearance(enforced=False, status="CLEAR",
                               reason="latest narrative_rubric verdict is CLEAR")
    acks = [
        r for r in records
        if r.get("event") == "narrative_rubric_ack"
        and r.get("inputs", {}).get("problem") == problem
        and (r.get("inputs", {}).get("confirmed_by") or "").strip()
        and r.get("ts", "") > latest.get("ts", "")
    ]
    if acks:
        ack = acks[-1]
        return RubricClearance(
            enforced=False, status="REQUIRES_HUMAN_VERIFICATION",
            reason=(f"REQUIRES_HUMAN_VERIFICATION acknowledged by "
                    f"{ack['inputs']['confirmed_by']} (narrative_rubric_ack at {ack.get('ts')})"),
        )
    return RubricClearance(
        enforced=True, status="REQUIRES_HUMAN_VERIFICATION",
        reason=(f"latest narrative_rubric verdict is REQUIRES_HUMAN_VERIFICATION "
                f"(ts {latest.get('ts')}) with no later human acknowledgment"),
    )


def assert_promotable(records: list, problem: str) -> RubricClearance:
    """Refuse lock promotion while a failing rubric verdict governs `problem`.

    Raises ValueError on a blocked clearance; returns the clearance
    otherwise. This is the single validation both promotion paths
    (PROVISIONAL_LOCK advancement and third-party CONFIRM to LOCKED) call
    before mutating state, so LOCKED-with-failing-verdict cannot arise.
    """
    clearance = clearance_for_problem(records, problem)
    if clearance.enforced:
        raise ValueError(
            f"Lock promotion blocked for problem '{problem}': {clearance.reason}. "
            f"Clear by human acknowledgment (narrative_rubric_ack with confirmed_by) "
            f"or regenerate the narrative until the rubric grades CLEAR."
        )
    return clearance


def record_narrative_ack(ledger, *, problem: str, confirmed_by: str, note: str = "") -> str:
    """Append a four-eyes human acknowledgment for a failing rubric verdict.

    The ack event is what unlocks promotion; `confirmed_by` must name the
    human. Returns the ledger record id.
    """
    if not (confirmed_by or "").strip():
        raise ValueError("narrative_rubric_ack requires a named human in confirmed_by")
    return ledger.append(
        event="narrative_rubric_ack", actor="human-review",
        inputs={"problem": problem, "confirmed_by": confirmed_by, "note": note},
        sources=[confirmed_by], confidence=None,
        rationale=(f"Human acknowledgment clearing REQUIRES_HUMAN_VERIFICATION "
                   f"for '{problem}'" + (f" — {note}" if note else "")),
    )
