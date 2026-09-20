"""Row 35 enforcement: a failing rubric verdict BLOCKS lock promotion.

One label, one consequence: REQUIRES_HUMAN_VERIFICATION from the narrative
rubric behaves exactly like the CHP state machine's identically-named
status — promotion is refused until a named human acknowledges
(narrative_rubric_ack with confirmed_by) or the narrative is regenerated
and re-graded CLEAR.
"""

from __future__ import annotations

import tempfile
import unittest

from convergence.audit.ledger import AuditLedger
from convergence.chp.models import (
    DecisionCase,
    SessionStatus,
    ThirdPartyValidation,
    ValidationResult,
)
from convergence.chp.orchestrator import CHPOrchestrator
from convergence.chp.registry import DecisionRegistry
from convergence.mesh.rubric import (
    RubricResult,
    clearance_for_problem,
    record_narrative_ack,
)


def _case(decision_id: str = "D-01", title: str = "Analyze CoA mapping") -> DecisionCase:
    return DecisionCase(
        decision_id=decision_id, title=title, domain="coa_mapping",
        created_at="2026-09-20T00:00:00Z", owner="ops",
    )


def _verdict_record(problem: str, *, status: str, score: int, ts: str) -> dict:
    return {"ts": ts, "event": "narrative_rubric", "actor": "narrative_rubric",
            "inputs": {"problem": problem, "status": status, "score": score,
                       "criteria": {}}}


def _ack_record(problem: str, *, confirmed_by: str, ts: str) -> dict:
    return {"ts": ts, "event": "narrative_rubric_ack", "actor": "human-review",
            "inputs": {"problem": problem, "confirmed_by": confirmed_by, "note": ""}}


def _wired_orchestrator(records: list) -> CHPOrchestrator:
    registry = DecisionRegistry()
    case = _case()
    registry._cases = getattr(registry, "_cases", {})
    if hasattr(registry, "add"):
        registry.add(case)
    else:
        registry._cases = {case.decision_id: case}
    return CHPOrchestrator(registry=registry, ledger=_FakeLedger(records))


class _FakeLedger:
    """Stands in for AuditLedger in unit tests; read_all() returns fixed records."""

    def __init__(self, records: list):
        self._records = records

    def read_all(self):
        return list(self._records)


class TestRubricBlocksPromotion(unittest.TestCase):
    def test_failing_rubric_blocks_provisional_lock(self):
        records = [_verdict_record("Analyze CoA mapping", status="REQUIRES_HUMAN_VERIFICATION",
                                   score=70, ts="2026-09-20T10:00:00Z")]
        orch = _wired_orchestrator(records)
        with self.assertRaises(ValueError) as ctx:
            orch.advance_to_provisional_lock("D-01")
        self.assertIn("REQUIRES_HUMAN_VERIFICATION", str(ctx.exception))
        # The case was NOT mutated.
        self.assertEqual(orch.registry.get("D-01").status, SessionStatus.EXPLORING)

    def test_human_acknowledgment_unlocks_promotion(self):
        records = [
            _verdict_record("Analyze CoA mapping", status="REQUIRES_HUMAN_VERIFICATION",
                            score=70, ts="2026-09-20T10:00:00Z"),
            _ack_record("Analyze CoA mapping", confirmed_by="shyam", ts="2026-09-20T11:00:00Z"),
        ]
        orch = _wired_orchestrator(records)
        case = orch.advance_to_provisional_lock("D-01")
        self.assertEqual(case.status, SessionStatus.PROVISIONAL_LOCK)

    def test_clear_verdict_proceeds(self):
        records = [_verdict_record("Analyze CoA mapping", status="CLEAR",
                                   score=100, ts="2026-09-20T10:00:00Z")]
        orch = _wired_orchestrator(records)
        case = orch.advance_to_provisional_lock("D-01")
        self.assertEqual(case.status, SessionStatus.PROVISIONAL_LOCK)

    def test_locked_with_failing_rubric_is_refused(self):
        records = [_verdict_record("Analyze CoA mapping", status="REQUIRES_HUMAN_VERIFICATION",
                                   score=70, ts="2026-09-20T10:00:00Z")]
        orch = _wired_orchestrator(records)
        confirm = ThirdPartyValidation(
            validator="external-review", item="CoA mapping locked",
            challenge="confirm the mapping", result=ValidationResult.CONFIRM,
            rationale="evidence reviewed",
        )
        with self.assertRaises(ValueError):
            orch.apply_validation("D-01", confirm)
        # Status unchanged — the refusal happened before mutation.
        self.assertEqual(orch.registry.get("D-01").status, SessionStatus.EXPLORING)

    def test_no_verdict_no_ceremony(self):
        # CHP-only flows without a graded narrative proceed as before.
        orch = _wired_orchestrator([])
        case = orch.advance_to_provisional_lock("D-01")
        self.assertEqual(case.status, SessionStatus.PROVISIONAL_LOCK)

    def test_stale_ack_after_new_failing_verdict_does_not_clear(self):
        # A new failing verdict AFTER the human ack re-blocks: the ack clears
        # only verdicts that came before it.
        records = [
            _verdict_record("Analyze CoA mapping", status="REQUIRES_HUMAN_VERIFICATION",
                            score=70, ts="2026-09-20T10:00:00Z"),
            _ack_record("Analyze CoA mapping", confirmed_by="shyam", ts="2026-09-20T11:00:00Z"),
            _verdict_record("Analyze CoA mapping", status="REQUIRES_HUMAN_VERIFICATION",
                            score=45, ts="2026-09-20T12:00:00Z"),
        ]
        clearance = clearance_for_problem(records, "Analyze CoA mapping")
        self.assertTrue(clearance.enforced)


class TestClearanceScanning(unittest.TestCase):
    def test_ack_without_name_is_ignored(self):
        records = [
            _verdict_record("p", status="REQUIRES_HUMAN_VERIFICATION", score=70,
                            ts="2026-09-20T10:00:00Z"),
            _ack_record("p", confirmed_by="   ", ts="2026-09-20T11:00:00Z"),
        ]
        self.assertTrue(clearance_for_problem(records, "p").enforced)

    def test_ack_for_other_problem_is_ignored(self):
        records = [
            _verdict_record("p1", status="REQUIRES_HUMAN_VERIFICATION", score=70,
                            ts="2026-09-20T10:00:00Z"),
            _ack_record("p2", confirmed_by="shyam", ts="2026-09-20T11:00:00Z"),
        ]
        self.assertTrue(clearance_for_problem(records, "p1").enforced)

    def test_latest_verdict_wins(self):
        records = [
            _verdict_record("p", status="REQUIRES_HUMAN_VERIFICATION", score=70,
                            ts="2026-09-20T10:00:00Z"),
            _verdict_record("p", status="CLEAR", score=100, ts="2026-09-20T11:00:00Z"),
        ]
        self.assertFalse(clearance_for_problem(records, "p").enforced)

    def test_record_narrative_ack_requires_a_named_human(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = AuditLedger(path=f"{tmp}/ledger.jsonl", key="k")
            with self.assertRaises(ValueError):
                record_narrative_ack(led, problem="p", confirmed_by="  ")
            record_narrative_ack(led, problem="p", confirmed_by="shyam", note="reviewed evidence")
            events = [r["event"] for r in led.read_all()]
            self.assertIn("narrative_rubric_ack", events)


if __name__ == "__main__":
    unittest.main()
