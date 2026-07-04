"""Tests for the signed audit ledger and the stigmergy coordination board."""
import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from convergence.audit import AuditLedger, compute_sig
from convergence.audit.ledger import TEST_DEFAULT_KEY, resolve_key
from convergence.stigmergy.board import (
    DECAY_CONSTANTS,
    GC_THRESHOLD,
    SignalType,
    StigmergyBoard,
)
from convergence.mesh.orchestrator import EnterpriseOrchestrator
from convergence.workstreams.base import WorkstreamBrief
from convergence.workstreams.coa_mapping import CoAMappingWorkstream


# ============================================================
# SIGNED AUDIT LEDGER
# ============================================================

class TestAuditLedger(unittest.TestCase):
    def _ledger(self, key="test-key"):
        path = tempfile.mktemp(suffix=".jsonl")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return AuditLedger(path, key=key), path

    def test_append_returns_sig_and_writes_record(self):
        led, _ = self._ledger()
        sig = led.append(event="recommendation", actor="finance",
                         inputs={"problem": "map coa"}, sources=["trial_balance"],
                         confidence="high", rationale="Map 1:1 where clean")
        self.assertEqual(len(sig), 64)
        recs = led.read_all()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["event"], "recommendation")
        self.assertEqual(recs[0]["actor"], "finance")
        self.assertEqual(recs[0]["confidence"], "high")
        self.assertEqual(recs[0]["prev_sig"], "")
        self.assertEqual(recs[0]["sig"], sig)

    def test_optional_fields_omitted(self):
        led, _ = self._ledger()
        led.append(event="board_narrative", actor="orchestrator", inputs={}, sources=[])
        rec = led.read_all()[0]
        self.assertNotIn("confidence", rec)
        self.assertNotIn("rationale", rec)

    def test_chain_links_prev_sig(self):
        led, _ = self._ledger()
        s1 = led.append(event="e1", actor="a", inputs={}, sources=[])
        s2 = led.append(event="e2", actor="b", inputs={}, sources=[])
        recs = led.read_all()
        self.assertEqual(recs[0]["prev_sig"], "")
        self.assertEqual(recs[1]["prev_sig"], s1)
        self.assertNotEqual(s1, s2)

    def test_verify_clean(self):
        led, _ = self._ledger()
        for i in range(5):
            led.append(event=f"e{i}", actor="a", inputs={"i": i}, sources=[])
        intact, first_bad = led.verify()
        self.assertTrue(intact)
        self.assertIsNone(first_bad)

    def test_verify_empty_is_intact(self):
        led, _ = self._ledger()
        intact, first_bad = led.verify()
        self.assertTrue(intact)
        self.assertIsNone(first_bad)

    def test_tamper_detection_first_index(self):
        led, path = self._ledger()
        for i in range(4):
            led.append(event=f"e{i}", actor="a", inputs={"i": i}, sources=[],
                       rationale=f"claim {i}")
        with open(path) as fh:
            lines = fh.read().splitlines()
        rec = json.loads(lines[2])
        rec["rationale"] = "TAMPERED"
        lines[2] = json.dumps(rec)
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        intact, first_bad = led.verify()
        self.assertFalse(intact)
        self.assertEqual(first_bad, 2)

    def test_deletion_breaks_chain(self):
        led, path = self._ledger()
        for i in range(4):
            led.append(event=f"e{i}", actor="a", inputs={"i": i}, sources=[])
        with open(path) as fh:
            lines = fh.read().splitlines()
        del lines[1]
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        intact, first_bad = led.verify()
        self.assertFalse(intact)
        self.assertEqual(first_bad, 1)

    def test_wrong_key_fails(self):
        led, path = self._ledger(key="right")
        led.append(event="e", actor="a", inputs={}, sources=[])
        other = AuditLedger(path, key="wrong")
        intact, first_bad = other.verify()
        self.assertFalse(intact)
        self.assertEqual(first_bad, 0)

    def test_key_resolution(self):
        os.environ.pop("AUDIT_LEDGER_KEY", None)
        self.assertEqual(resolve_key(), TEST_DEFAULT_KEY)
        os.environ["AUDIT_LEDGER_KEY"] = "env-key"
        try:
            self.assertEqual(resolve_key(), "env-key")
            self.assertEqual(resolve_key("explicit"), "explicit")
        finally:
            os.environ.pop("AUDIT_LEDGER_KEY", None)

    def test_sig_matches_manual(self):
        led, _ = self._ledger(key="k")
        led.append(event="e", actor="a", inputs={"x": 1}, sources=["s"],
                   ts="2026-01-01T00:00:00+00:00")
        rec = led.read_all()[0]
        self.assertEqual(rec["sig"], compute_sig("k", rec, ""))


# ============================================================
# STIGMERGY BOARD
# ============================================================

class TestStigmergyBoard(unittest.TestCase):
    def test_deposit_and_read(self):
        board = StigmergyBoard()
        board.deposit(agent="finance", signal_type=SignalType.FINDING,
                      key="coa", content="map clean lines 1:1", strength=1.0)
        signals = board.read(signal_type=SignalType.FINDING)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].agent, "finance")
        self.assertEqual(signals[0].content, "map clean lines 1:1")

    def test_read_by_region_key(self):
        board = StigmergyBoard()
        board.deposit(agent="a", signal_type=SignalType.DEPENDENCY_NOTE,
                      key="account_mapping", content="available")
        board.deposit(agent="b", signal_type=SignalType.DEPENDENCY_NOTE,
                      key="kpi_alignment", content="available")
        hits = board.read(key="account_mapping")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].key, "account_mapping")

    def test_exclude_agent(self):
        board = StigmergyBoard()
        board.deposit(agent="finance", signal_type=SignalType.FINDING, content="x")
        board.deposit(agent="strategy", signal_type=SignalType.FINDING, content="y")
        hits = board.read(exclude_agent="finance")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].agent, "strategy")

    def test_time_decay_reduces_strength(self):
        board = StigmergyBoard()
        sig = board.deposit(agent="a", signal_type=SignalType.FINDING,
                            content="c", strength=1.0)
        now = sig.deposited_at
        half_life = math.log(2) / DECAY_CONSTANTS[SignalType.FINDING]
        fresh = sig.current_strength(now)
        decayed = sig.current_strength(now + half_life)
        self.assertAlmostEqual(fresh, 1.0, places=6)
        self.assertAlmostEqual(decayed, 0.5, places=3)  # one half-life -> 50%

    def test_read_applies_decay_and_ttl(self):
        board = StigmergyBoard()
        sig = board.deposit(agent="a", signal_type=SignalType.CONFIDENCE,
                            content="high", strength=1.0)
        # Far in the future: past TTL -> not returned.
        future = sig.deposited_at + sig.ttl_seconds + 1
        self.assertEqual(len(board.read(now=future)), 0)

    def test_read_strength_aggregates(self):
        board = StigmergyBoard()
        board.deposit(agent="a", signal_type=SignalType.RISK_FLAG, key="coa",
                      content="r1", strength=1.0)
        board.deposit(agent="b", signal_type=SignalType.RISK_FLAG, key="coa",
                      content="r2", strength=1.0)
        total = board.read_strength(signal_type=SignalType.RISK_FLAG, key="coa")
        self.assertAlmostEqual(total, 2.0, places=2)

    def test_evaporate_purges_expired(self):
        board = StigmergyBoard()
        sig = board.deposit(agent="a", signal_type=SignalType.PROGRESS
                            if hasattr(SignalType, "PROGRESS") else SignalType.CONFIDENCE,
                            content="c", strength=1.0)
        self.assertEqual(board.count(), 1)
        future = sig.deposited_at + sig.ttl_seconds + 1
        purged = board.garbage_collect(now=future)
        self.assertEqual(purged, 1)
        self.assertEqual(board.count(), 0)

    def test_gc_threshold_constant(self):
        # Signals decayed below GC_THRESHOLD are treated as expired.
        board = StigmergyBoard()
        sig = board.deposit(agent="a", signal_type=SignalType.FINDING,
                            content="c", strength=1.0)
        # Time at which strength falls just below threshold.
        lam = DECAY_CONSTANTS[SignalType.FINDING]
        t_expire = sig.deposited_at + (math.log(1.0 / GC_THRESHOLD) / lam) + 1
        self.assertTrue(sig.is_expired(t_expire))

    def test_context_for_excludes_own_and_limits(self):
        board = StigmergyBoard()
        for i in range(20):
            board.deposit(agent="peer", signal_type=SignalType.FINDING,
                          content=f"finding {i}", strength=1.0)
        board.deposit(agent="me", signal_type=SignalType.FINDING, content="mine")
        ctx = board.context_for("me", limit=12)
        self.assertLessEqual(len(ctx), 12)
        self.assertTrue(all(s["agent"] != "me" for s in ctx))

    def test_deposit_records_to_ledger(self):
        path = tempfile.mktemp(suffix=".jsonl")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        led = AuditLedger(path, key="k")
        board = StigmergyBoard(ledger=led)
        board.deposit(agent="finance", signal_type=SignalType.FINDING, content="x")
        recs = led.read_all()
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["event"], "stigmergy_deposit")
        self.assertEqual(recs[0]["actor"], "finance")


# ============================================================
# ORCHESTRATOR WIRING (stigmergy + ledger)
# ============================================================

class TestOrchestratorStigmergyWiring(unittest.TestCase):
    def _ws(self):
        return CoAMappingWorkstream(
            WorkstreamBrief(title="CoA", acquirer="A", target="B", day_post_close=53)
        )

    def test_ledger_default_signs_recommendations(self):
        ws = self._ws()
        path = tempfile.mktemp(suffix=".jsonl")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        led = AuditLedger(path, key="k")
        orch = EnterpriseOrchestrator(agents=ws.agents, context=ws.context, ledger=led)
        orch.orchestrate("Analyze CoA mapping")
        events = [r["event"] for r in led.read_all()]
        self.assertEqual(events.count("recommendation"), 3)
        self.assertIn("board_narrative", events)
        intact, first_bad = led.verify()
        self.assertTrue(intact)
        self.assertIsNone(first_bad)

    def test_stigmergy_preserves_topological_order(self):
        ws = self._ws()
        path = tempfile.mktemp(suffix=".jsonl")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        led = AuditLedger(path, key="k")
        orch = EnterpriseOrchestrator(agents=ws.agents, context=ws.context,
                                      ledger=led, use_stigmergy=True)
        report = orch.orchestrate("Analyze CoA mapping")
        names = [t.agent for t in report.turns]
        self.assertLess(names.index("finance"), names.index("strategy"))
        self.assertLess(names.index("strategy"), names.index("compliance"))
        # Board received deposits and the chain still verifies.
        self.assertGreater(orch.board.count(), 0)
        self.assertTrue(led.verify()[0])

    def test_no_stigmergy_by_default(self):
        ws = self._ws()
        orch = EnterpriseOrchestrator(agents=ws.agents, context=ws.context)
        self.assertIsNone(orch.board)


if __name__ == "__main__":
    unittest.main()
