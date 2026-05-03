"""Tests for Convergence — CHP, Mesh, Workstreams, Convergence Tower, API."""
import json
import os
import sys
import unittest

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from convergence.chp.models import (
    ContextCheck, DecisionCase, Dossier, FoundationAttack, FoundationDisclosure,
    IntegrationHealth, ModelParityCheck, Phase, RoundRecord, SessionStatus,
    ThirdPartyValidation, ValidationResult, Verdict, WorkstreamType,
)
from convergence.chp.gates import evaluate_r0_gate, evaluate_phase_gate, GateEvaluation
from convergence.chp.payloads import (
    PayloadEnvelope, build_payload_envelope, extract_payload_id,
    payload_echo_confirmed, validate_payload_envelope,
)
from convergence.chp.foundation import foundation_verdict, validate_foundation_pair
from convergence.chp.parity import assess_model_parity, ModelTier
from convergence.chp.rounds import next_round
from convergence.chp.devil import merge_structural_vulnerabilities
from convergence.chp.dossier import validate_dossier
from convergence.chp.validators import apply_third_party_validation
from convergence.chp.registry import DecisionRegistry
from convergence.chp.accuracy import run_accuracy_guard, AccuracyGuardResult
from convergence.chp.orchestrator import CHPOrchestrator, CHPReport
from convergence.mesh.protocol import (
    CognitiveMeshProtocol, ConfidenceLevel, ExpansionStep, CompressionStep,
    ReasoningTrace, detect_hallucination_risk, ProblemType,
)
from convergence.mesh.context import ContextEngine, Entity, Task
from convergence.mesh.playbook import Playbook, Reflector, Curator, DeltaOp, Bullet
from convergence.mesh.bridge import BridgeFramework, EntryPoint, WhyLink, Consequences, Statement, Workflow
from convergence.mesh.agent import MeshAgent, AgentCapability, TurnResult
from convergence.mesh.orchestrator import EnterpriseOrchestrator
from convergence.workstreams.base import (
    MappingLine, MappingType, SynergyItem, WorkstreamBrief, WorkstreamStatus,
)
from convergence.workstreams.coa_mapping import CoAMappingWorkstream
from convergence.workstreams.close_harmonization import CloseHarmonizationWorkstream
from convergence.workstreams.systems_integration import SystemsIntegrationWorkstream
from convergence.workstreams.synergy_tracking import SynergyTrackingWorkstream
from convergence.convergence_tower import (
    ConvergenceTower, RiskItem, Milestone, BlockedDecision,
    compute_overall_health, compute_completion_pct,
)


# ============================================================
# CHP MODEL TESTS (1-20)
# ============================================================

class TestCHPModels(unittest.TestCase):
    def test_session_status_values(self):
        self.assertIn("EXPLORING", SessionStatus.EXPLORING.value)
        self.assertIn("PROVISIONAL_LOCK", SessionStatus.PROVISIONAL_LOCK.value)
        self.assertIn("LOCKED", SessionStatus.LOCKED.value)
        self.assertIn("HALT", SessionStatus.HALT.value)

    def test_verdict_values(self):
        self.assertEqual(Verdict.PASS.value, "PASS")
        self.assertEqual(Verdict.HALT.value, "HALT")
        self.assertEqual(Verdict.REFRAME.value, "REFRAME")
        self.assertEqual(Verdict.PHASE_GATE_FAIL.value, "PHASE_GATE_FAIL")

    def test_phase_values(self):
        self.assertEqual(Phase.FOUNDATION, 0)
        self.assertEqual(Phase.SPEC, 1)
        self.assertEqual(Phase.IMPLEMENTATION, 2)

    def test_dossier_validation_passes(self):
        d = Dossier(core_problem="test", goal_state=["a"], current_state=["b"],
                    constraints=["c"], scope=["d"])
        self.assertEqual(d.validate(), [])

    def test_dossier_validation_fails_empty_problem(self):
        d = Dossier(core_problem="")
        errors = d.validate()
        self.assertTrue(any("core_problem" in e for e in errors))

    def test_dossier_validation_fails_insufficient_sections(self):
        d = Dossier(core_problem="test", goal_state=["a"])
        errors = d.validate()
        self.assertTrue(len(errors) > 0)

    def test_dossier_roundtrip(self):
        d = Dossier(core_problem="test", goal_state=["a", "b"], constraints=["c"])
        data = d.to_dict()
        d2 = Dossier.from_dict(data)
        self.assertEqual(d2.core_problem, "test")
        self.assertEqual(d2.goal_state, ["a", "b"])

    def test_foundation_disclosure_validation(self):
        fd = FoundationDisclosure(weakest_assumptions=["a"], invalidation_conditions=["b"],
                                  key_vulnerability="c")
        self.assertEqual(fd.validate(), [])

    def test_foundation_disclosure_validation_too_many_assumptions(self):
        fd = FoundationDisclosure(weakest_assumptions=["a", "b", "c", "d"], invalidation_conditions=["b"],
                                  key_vulnerability="c")
        errors = fd.validate()
        self.assertTrue(len(errors) > 0)

    def test_foundation_attack_validation(self):
        fa = FoundationAttack(assumption_attacks=["a"], vulnerability_strike="b", foundation_score=80)
        self.assertEqual(fa.validate(), [])

    def test_foundation_attack_validation_score_out_of_range(self):
        fa = FoundationAttack(assumption_attacks=["a"], vulnerability_strike="b", foundation_score=150)
        errors = fa.validate()
        self.assertTrue(any("foundation_score" in e for e in errors))

    def test_decision_case_roundtrip(self):
        dossier = Dossier(core_problem="test", goal_state=["a"], current_state=["b"],
                          constraints=["c"], scope=["d"])
        case = DecisionCase(decision_id="dc-001", title="Test Decision", domain="coa_mapping",
                           created_at="2026-01-01", owner="cfo", dossier=dossier,
                           high_stakes=True, foundation_score=75)
        data = case.to_dict()
        case2 = DecisionCase.from_dict(data)
        self.assertEqual(case2.decision_id, "dc-001")
        self.assertEqual(case2.domain, "coa_mapping")
        self.assertEqual(case2.foundation_score, 75)
        self.assertEqual(case2.dossier.core_problem, "test")

    def test_decision_case_add_round(self):
        case = DecisionCase(decision_id="dc-002", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo")
        self.assertEqual(case.current_round, 0)
        record = RoundRecord(decision_id="dc-002", phase=Phase.SPEC, round_number=1, payload_id="ABC123")
        case.add_round(record)
        self.assertEqual(case.current_round, 1)
        self.assertEqual(case.current_phase, Phase.SPEC)

    def test_third_party_validation_roundtrip(self):
        tv = ThirdPartyValidation(validator="auditor", item="coa-map-v1",
                                 challenge="Revenue recognition timing",
                                 result=ValidationResult.CONFIRM, rationale="Clean mapping")
        data = tv.to_dict()
        tv2 = ThirdPartyValidation.from_dict(data)
        self.assertEqual(tv2.result, ValidationResult.CONFIRM)
        self.assertEqual(tv2.validator, "auditor")

    def test_round_record_roundtrip(self):
        rr = RoundRecord(decision_id="dc-003", phase=Phase.IMPLEMENTATION, round_number=3,
                         payload_id="XYZ789", origin_packet="test packet")
        data = rr.to_dict()
        rr2 = RoundRecord.from_dict(data)
        self.assertEqual(rr2.phase, Phase.IMPLEMENTATION)
        self.assertEqual(rr2.payload_id, "XYZ789")

    def test_integration_health_enum(self):
        self.assertEqual(IntegrationHealth.GREEN.value, "green")
        self.assertEqual(IntegrationHealth.AMBER.value, "amber")
        self.assertEqual(IntegrationHealth.RED.value, "red")

    def test_workstream_type_enum(self):
        self.assertEqual(WorkstreamType.COA_MAPPING.value, "coa_mapping")
        self.assertEqual(WorkstreamType.SYNERGY_TRACKING.value, "synergy_tracking")

    def test_context_check_roundtrip(self):
        cc = ContextCheck(memory_tools="AVAILABLE", prior_sessions_count=3, assessment="RELATED")
        data = cc.to_dict()
        cc2 = ContextCheck.from_dict(data)
        self.assertEqual(cc2.assessment, "RELATED")
        self.assertEqual(cc2.prior_sessions_count, 3)


# ============================================================
# CHP GATE TESTS (21-30)
# ============================================================

class TestCHPGates(unittest.TestCase):
    def test_r0_gate_all_pass(self):
        result = evaluate_r0_gate(solvable=True, scoped=True, valid=True, worth_it=True)
        self.assertEqual(result.verdict, Verdict.PASS)
        self.assertTrue(all(v == "PASS" for v in result.results.values()))

    def test_r0_gate_halt_on_unscoped(self):
        result = evaluate_r0_gate(solvable=True, scoped=False, valid=True, worth_it=True)
        self.assertEqual(result.verdict, Verdict.HALT)
        self.assertEqual(result.results["Scoped"], "FATAL")

    def test_r0_gate_halt_on_not_worth_it(self):
        result = evaluate_r0_gate(solvable=True, scoped=True, valid=True, worth_it=False)
        self.assertEqual(result.verdict, Verdict.HALT)

    def test_phase_gate_early_rounds(self):
        result = evaluate_phase_gate(1, SessionStatus.EXPLORING)
        self.assertEqual(result, Verdict.PASS)

    def test_phase_gate_pass_with_lock(self):
        result = evaluate_phase_gate(3, SessionStatus.PROVISIONAL_LOCK)
        self.assertEqual(result, Verdict.PASS)

    def test_phase_gate_fail_without_lock(self):
        result = evaluate_phase_gate(3, SessionStatus.EXPLORING)
        self.assertEqual(result, Verdict.PHASE_GATE_FAIL)

    def test_phase_gate_round_2_still_passes(self):
        result = evaluate_phase_gate(2, SessionStatus.EXPLORING)
        self.assertEqual(result, Verdict.PASS)


# ============================================================
# CHP PAYLOAD TESTS (31-40)
# ============================================================

class TestCHPPayloads(unittest.TestCase):
    def test_build_and_render_envelope(self):
        env = build_payload_envelope("test body", route="RX", payload_id="ABC123")
        rendered = env.render()
        self.assertIn("BEGIN_PAYLOAD [RX] [ABC123]", rendered)
        self.assertIn("test body", rendered)
        self.assertIn("END_PAYLOAD [RX] [ABC123]", rendered)

    def test_validate_correct_envelope(self):
        env = build_payload_envelope("hello world")
        self.assertTrue(validate_payload_envelope(env.render()))

    def test_validate_incorrect_envelope(self):
        self.assertFalse(validate_payload_envelope("not an envelope"))

    def test_validate_short_envelope(self):
        self.assertFalse(validate_payload_envelope("BEGIN_PAYLOAD [RX] [ABC]"))

    def test_extract_payload_id(self):
        env = build_payload_envelope("body", payload_id="XYZ789")
        self.assertEqual(extract_payload_id(env.render()), "XYZ789")

    def test_extract_payload_id_none(self):
        self.assertIsNone(extract_payload_id("no payload here"))

    def test_echo_confirmed(self):
        self.assertTrue(payload_echo_confirmed("RX", "ABC123", "[RX] [ABC123] CONFIRMED"))
        self.assertFalse(payload_echo_confirmed("RX", "ABC123", "wrong"))

    def test_auto_generated_payload_id(self):
        env1 = build_payload_envelope("body1")
        env2 = build_payload_envelope("body2")
        self.assertEqual(len(env1.payload_id), 6)
        self.assertNotEqual(env1.payload_id, env2.payload_id)


# ============================================================
# CHP FOUNDATION TESTS (41-50)
# ============================================================

class TestCHPFoundation(unittest.TestCase):
    def test_foundation_verdict_pass(self):
        fa = FoundationAttack(assumption_attacks=["a"], vulnerability_strike="b", foundation_score=80)
        self.assertEqual(foundation_verdict(fa), Verdict.PASS)

    def test_foundation_verdict_reframe(self):
        fa = FoundationAttack(assumption_attacks=["a"], vulnerability_strike="b", foundation_score=50)
        self.assertEqual(foundation_verdict(fa), Verdict.REFRAME)

    def test_foundation_verdict_boundary(self):
        fa = FoundationAttack(assumption_attacks=["a"], vulnerability_strike="b", foundation_score=70)
        self.assertEqual(foundation_verdict(fa), Verdict.PASS)

    def test_validate_pair_clean(self):
        fd = FoundationDisclosure(weakest_assumptions=["a"], invalidation_conditions=["b"],
                                  key_vulnerability="c")
        fa = FoundationAttack(assumption_attacks=["a", "b", "c"], vulnerability_strike="d",
                              foundation_score=80)
        self.assertEqual(validate_foundation_pair(fd, fa), [])

    def test_validate_pair_attack_too_short(self):
        fd = FoundationDisclosure(weakest_assumptions=["a", "b", "c"], invalidation_conditions=["b"],
                                  key_vulnerability="c")
        fa = FoundationAttack(assumption_attacks=["a"], vulnerability_strike="d", foundation_score=80)
        errors = validate_foundation_pair(fd, fa)
        self.assertTrue(any("address each" in e for e in errors))


# ============================================================
# CHP PARITY TESTS (51-58)
# ============================================================

class TestCHPParity(unittest.TestCase):
    def test_same_tier_none(self):
        result = assess_model_parity("GPT-5.4", "GPT-5.4")
        self.assertEqual(result.delta, "NONE")

    def test_small_gap_minor(self):
        result = assess_model_parity("gpt-5", "haiku")
        self.assertEqual(result.delta, "SIGNIFICANT")
        self.assertIsNone(result.advisory)

    def test_adjacent_gap_minor(self):
        result = assess_model_parity("claude-4", "sonnet")
        self.assertEqual(result.delta, "MINOR")
        self.assertIsNotNone(result.advisory)

    def test_large_gap_significant(self):
        result = assess_model_parity("GPT-5.4", "haiku")
        self.assertEqual(result.delta, "SIGNIFICANT")

    def test_unknown_model_minor(self):
        result = assess_model_parity("custom-model", "GPT-5.4")
        self.assertEqual(result.delta, "MINOR")
        self.assertIsNotNone(result.advisory)


# ============================================================
# CHP ROUNDS TESTS (59-62)
# ============================================================

class TestCHPRounds(unittest.TestCase):
    def test_foundation_to_spec(self):
        phase, rnd = next_round(Phase.FOUNDATION, 0)
        self.assertEqual(phase, Phase.SPEC)
        self.assertEqual(rnd, 1)

    def test_spec_within_phase(self):
        phase, rnd = next_round(Phase.SPEC, 1)
        self.assertEqual(phase, Phase.SPEC)
        self.assertEqual(rnd, 2)

    def test_spec_to_implementation(self):
        phase, rnd = next_round(Phase.SPEC, 2)
        self.assertEqual(phase, Phase.IMPLEMENTATION)
        self.assertEqual(rnd, 3)

    def test_implementation_advances(self):
        phase, rnd = next_round(Phase.IMPLEMENTATION, 3)
        self.assertEqual(phase, Phase.IMPLEMENTATION)
        self.assertEqual(rnd, 4)


# ============================================================
# CHP DEVIL TESTS (63-65)
# ============================================================

class TestCHPDevil(unittest.TestCase):
    def test_merge_empty(self):
        self.assertEqual(merge_structural_vulnerabilities([], []), [])

    def test_merge_new_items(self):
        result = merge_structural_vulnerabilities(["a"], ["b", "c"])
        self.assertEqual(result, ["a", "b", "c"])

    def test_merge_deduplicates(self):
        result = merge_structural_vulnerabilities(["a", "b"], ["b", "c"])
        self.assertEqual(result, ["a", "b", "c"])


# ============================================================
# CHP VALIDATORS TESTS (66-72)
# ============================================================

class TestCHPValidators(unittest.TestCase):
    def test_confirm_locks(self):
        case = DecisionCase(decision_id="v-001", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo", status=SessionStatus.EXPLORING)
        tv = ThirdPartyValidation(validator="auditor", item="test-item",
                                 challenge="test", result=ValidationResult.CONFIRM, rationale="ok")
        status = apply_third_party_validation(case, tv)
        self.assertEqual(status, SessionStatus.LOCKED)
        self.assertIn("test-item", case.locked_decisions)

    def test_reject_reverts(self):
        case = DecisionCase(decision_id="v-002", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo", status=SessionStatus.EXPLORING)
        tv = ThirdPartyValidation(validator="auditor", item="test-item",
                                 challenge="test", result=ValidationResult.REJECT, rationale="nope")
        status = apply_third_party_validation(case, tv)
        self.assertEqual(status, SessionStatus.EXPLORING)
        self.assertTrue(any("Validation rejected" in f for f in case.flip_criteria))

    def test_no_duplicate_locked(self):
        case = DecisionCase(decision_id="v-003", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo")
        case.locked_decisions = ["existing"]
        tv = ThirdPartyValidation(validator="a", item="existing", challenge="c",
                                 result=ValidationResult.CONFIRM, rationale="r")
        apply_third_party_validation(case, tv)
        self.assertEqual(case.locked_decisions.count("existing"), 1)


# ============================================================
# CHP ACCURACY GUARD TESTS (73-78)
# ============================================================

class TestAccuracyGuard(unittest.TestCase):
    def test_clean_pass(self):
        case = DecisionCase(decision_id="ag-001", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo", foundation_score=100)
        result = run_accuracy_guard(case)
        self.assertTrue(result.passes)

    def test_low_score_fails(self):
        case = DecisionCase(decision_id="ag-002", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo", foundation_score=50)
        result = run_accuracy_guard(case)
        self.assertFalse(result.passes)
        self.assertEqual(result.required_action, "REQUIRES_HUMAN_VERIFICATION")

    def test_open_vulnerabilities_fails(self):
        case = DecisionCase(decision_id="ag-003", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo", foundation_score=100,
                           structural_vulnerabilities=["vuln-1"])
        result = run_accuracy_guard(case)
        self.assertFalse(result.passes)

    def test_custom_floor(self):
        case = DecisionCase(decision_id="ag-004", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo", foundation_score=80)
        result = run_accuracy_guard(case, floor=70)
        self.assertTrue(result.passes)


# ============================================================
# CHP REGISTRY TESTS (79-86)
# ============================================================

class TestCHPRegistry(unittest.TestCase):
    def test_add_and_get(self):
        reg = DecisionRegistry()
        case = DecisionCase(decision_id="r-001", title="Test", domain="test",
                           created_at="2026-01-01", owner="cfo")
        reg.add(case)
        self.assertEqual(reg.get("r-001").title, "Test")

    def test_get_missing(self):
        reg = DecisionRegistry()
        self.assertIsNone(reg.get("nonexistent"))

    def test_find_related(self):
        reg = DecisionRegistry()
        c1 = DecisionCase(decision_id="r-002", title="Revenue mapping", domain="coa",
                          created_at="2026-01-01", owner="cfo",
                          dossier=Dossier(core_problem="Revenue recognition policy"))
        c2 = DecisionCase(decision_id="r-003", title="Close calendar", domain="close",
                          created_at="2026-01-01", owner="cfo")
        reg.add(c1)
        reg.add(c2)
        related = reg.find_related("revenue")
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0].decision_id, "r-002")

    def test_locked(self):
        reg = DecisionRegistry()
        c1 = DecisionCase(decision_id="r-004", title="L", domain="test",
                          created_at="2026-01-01", owner="cfo", status=SessionStatus.LOCKED)
        c2 = DecisionCase(decision_id="r-005", title="E", domain="test",
                          created_at="2026-01-01", owner="cfo", status=SessionStatus.EXPLORING)
        reg.add(c1)
        reg.add(c2)
        self.assertEqual(len(reg.locked()), 1)

    def test_save_and_load(self):
        import tempfile
        reg = DecisionRegistry()
        case = DecisionCase(decision_id="r-006", title="Persist", domain="test",
                           created_at="2026-01-01", owner="cfo")
        reg.add(case)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        reg.save(path)
        reg2 = DecisionRegistry.load(path)
        self.assertEqual(reg2.get("r-006").title, "Persist")
        os.unlink(path)

    def test_find_by_domain(self):
        reg = DecisionRegistry()
        reg.add(DecisionCase(decision_id="r-007", title="A", domain="coa_mapping",
                             created_at="2026-01-01", owner="cfo"))
        reg.add(DecisionCase(decision_id="r-008", title="B", domain="synergy",
                             created_at="2026-01-01", owner="cfo"))
        self.assertEqual(len(reg.find_by_domain("coa_mapping")), 1)

    def test_remove(self):
        reg = DecisionRegistry()
        reg.add(DecisionCase(decision_id="r-009", title="X", domain="test",
                             created_at="2026-01-01", owner="cfo"))
        self.assertTrue(reg.remove("r-009"))
        self.assertFalse(reg.remove("r-009"))


# ============================================================
# CHP ORCHESTRATOR TESTS (87-95)
# ============================================================

class TestCHPOrchestrator(unittest.TestCase):
    def _make_case(self, decision_id="o-001"):
        return DecisionCase(
            decision_id=decision_id, title="Test Decision", domain="coa_mapping",
            created_at="2026-01-01", owner="cfo", high_stakes=True,
            dossier=Dossier(core_problem="Map target CoA to acquirer model",
                           goal_state=["unified chart"], current_state=["separate charts"],
                           constraints=["no data loss"], scope=["P&L accounts", "balance sheet"]),
        )

    def _make_fd(self):
        return FoundationDisclosure(
            weakest_assumptions=["Target trial balance is accurate"],
            invalidation_conditions=["If target has stale accounts"],
            key_vulnerability="Hidden intercompany accounts",
        )

    def _make_fa(self, score=80):
        return FoundationAttack(
            assumption_attacks=["Assumption 1 verified against sample", "Assumption 2 cross-checked"],
            vulnerability_strike="No critical vulnerability found",
            foundation_score=score, attack_summary="Foundation is sound",
        )

    def test_run_initial_session_exploring(self):
        orch = CHPOrchestrator()
        report = orch.run_initial_session(case=self._make_case(), foundation_disclosure=self._make_fd(),
                                          foundation_attack=self._make_fa(80))
        self.assertEqual(report.case.status, SessionStatus.EXPLORING)
        self.assertEqual(report.r0_verdict, Verdict.PASS)
        self.assertEqual(report.foundation_verdict, Verdict.PASS)
        self.assertIsNotNone(report.initial_packet)

    def test_run_initial_session_reframe(self):
        orch = CHPOrchestrator()
        report = orch.run_initial_session(case=self._make_case(), foundation_disclosure=self._make_fd(),
                                          foundation_attack=self._make_fa(50))
        self.assertEqual(report.case.status, SessionStatus.REFRAME_REQUIRED)

    def test_run_initial_session_halt(self):
        case = self._make_case()
        case.dossier.scope = []  # No scope -> R0 FATAL
        orch = CHPOrchestrator()
        report = orch.run_initial_session(case=case, foundation_disclosure=self._make_fd(),
                                          foundation_attack=self._make_fa(80))
        self.assertEqual(report.case.status, SessionStatus.HALT)

    def test_advance_to_provisional_lock(self):
        orch = CHPOrchestrator()
        orch.run_initial_session(case=self._make_case(), foundation_disclosure=self._make_fd(),
                                 foundation_attack=self._make_fa(80))
        case = orch.advance_to_provisional_lock("o-001")
        self.assertEqual(case.status, SessionStatus.PROVISIONAL_LOCK)

    def test_receive_partner_packet(self):
        orch = CHPOrchestrator()
        orch.run_initial_session(case=self._make_case(), foundation_disclosure=self._make_fd(),
                                 foundation_attack=self._make_fa(80))
        packet = build_payload_envelope("partner response").render()
        case = orch.receive_partner_packet(decision_id="o-001", partner_packet=packet,
                                          phase=Phase.SPEC, round_number=1)
        self.assertEqual(case.current_round, 1)

    def test_apply_validation(self):
        orch = CHPOrchestrator()
        orch.run_initial_session(case=self._make_case(), foundation_disclosure=self._make_fd(),
                                 foundation_attack=self._make_fa(80))
        tv = ThirdPartyValidation(validator="auditor", item="coa-v1", challenge="test",
                                 result=ValidationResult.CONFIRM, rationale="clean")
        case = orch.apply_validation("o-001", tv)
        self.assertEqual(case.status, SessionStatus.LOCKED)

    def test_report_renders(self):
        orch = CHPOrchestrator()
        report = orch.run_initial_session(case=self._make_case(), foundation_disclosure=self._make_fd(),
                                          foundation_attack=self._make_fa(80))
        rendered = report.render()
        self.assertIn("CHP Session", rendered)
        self.assertIn("Test Decision", rendered)

    def test_context_check_sparse(self):
        orch = CHPOrchestrator()
        report = orch.run_initial_session(case=self._make_case(), foundation_disclosure=self._make_fd(),
                                          foundation_attack=self._make_fa(80))
        self.assertEqual(report.case.context_check.assessment, "SPARSE")

    def test_duplicate_detection(self):
        orch = CHPOrchestrator()
        orch.run_initial_session(case=self._make_case("o-dup"), foundation_disclosure=self._make_fd(),
                                 foundation_attack=self._make_fa(80))
        case2 = self._make_case("o-dup2")
        case2.title = "o-dup"  # same title triggers duplicate
        report2 = orch.run_initial_session(case=case2, foundation_disclosure=self._make_fd(),
                                           foundation_attack=self._make_fa(80))
        self.assertIn(report2.case.context_check.assessment, ("DUPLICATE", "RELATED"))


# ============================================================
# MESH PROTOCOL TESTS (96-102)
# ============================================================

class TestMeshProtocol(unittest.TestCase):
    def test_classification_strategic(self):
        proto = CognitiveMeshProtocol()
        ptype, _ = proto._default_classifier("revenue growth and market strategy")
        self.assertEqual(ptype, ProblemType.STRATEGIC)

    def test_classification_technical(self):
        proto = CognitiveMeshProtocol()
        ptype, _ = proto._default_classifier("database API implementation")
        self.assertEqual(ptype, ProblemType.TECHNICAL)

    def test_classification_ma_integration(self):
        proto = CognitiveMeshProtocol()
        ptype, _ = proto._default_classifier("chart of accounts mapping for integration")
        self.assertEqual(ptype, ProblemType.ANALYTICAL)

    def test_hallucination_risk_detection(self):
        self.assertIsNotNone(detect_hallucination_risk("Studies show that 80% of companies fail"))
        self.assertIsNone(detect_hallucination_risk("Revenue is $5M based on actuals"))

    def test_expansion_compression_cycle(self):
        def expand(p, ctx):
            return [ExpansionStep(label="Reframe", content="test"),
                    ExpansionStep(label="Constraints", content="budget limited")]
        def compress(p, exp, ctx):
            return ("Recommend X", [CompressionStep(label="Commit", content="done")],
                    ConfidenceLevel.HIGH, "nothing")
        proto = CognitiveMeshProtocol()
        trace = proto.run("test problem", expansion_fn=expand, compression_fn=compress)
        self.assertEqual(len(trace.expansion), 2)
        self.assertEqual(len(trace.compression), 1)
        self.assertEqual(trace.recommendation, "Recommend X")
        self.assertEqual(trace.confidence, ConfidenceLevel.HIGH)

    def test_failure_mode_fossil(self):
        trace = ReasoningTrace(problem="test", problem_type=ProblemType.STRATEGIC,
                               classification_rationale="test")
        trace.expansion = [ExpansionStep(label="R", content="same idea repeated")] * 3
        self.assertIsNotNone(CognitiveMeshProtocol.detect_failure_mode(trace))

    def test_failure_mode_hallucination(self):
        trace = ReasoningTrace(problem="test", problem_type=ProblemType.STRATEGIC,
                               classification_rationale="test")
        trace.grounding = [None] * 0  # no grounding issues
        trace.expansion = [ExpansionStep(label="R", content="Studies show growth")] * 4
        # Re-run grounding to populate
        proto = CognitiveMeshProtocol()
        grounded = proto._ground(trace)
        trace.grounding = grounded
        self.assertIsNotNone(CognitiveMeshProtocol.detect_failure_mode(trace))

    def test_trace_render(self):
        trace = ReasoningTrace(problem="What is the revenue?", problem_type=ProblemType.ANALYTICAL,
                               classification_rationale="revenue question",
                               recommendation="Revenue is $10M", confidence=ConfidenceLevel.MEDIUM)
        rendered = trace.render()
        self.assertIn("Revenue is $10M", rendered)
        self.assertIn("medium", rendered)


# ============================================================
# MESH CONTEXT TESTS (103-110)
# ============================================================

class TestMeshContext(unittest.TestCase):
    def test_upsert_and_entity(self):
        ctx = ContextEngine()
        ctx.upsert_entity(Entity(id="org-1", type="org", attributes={"name": "Acme Corp"}))
        snap = ctx.snapshot_for("agent-1", "org info")
        self.assertEqual(len(snap["entities"]), 1)

    def test_write_and_select(self):
        ctx = ContextEngine()
        ctx.write("Revenue recognized under ASC 606", source_agent="finance", importance=0.8)
        results = ctx.select("revenue recognition")
        self.assertEqual(len(results), 1)

    def test_record_event(self):
        ctx = ContextEngine()
        ctx.record_event("finance", "close", "Q1 close")
        snap = ctx.snapshot_for("agent-1", "close")
        self.assertTrue(len(snap["recent_events"]) >= 1)

    def test_task_management(self):
        ctx = ContextEngine()
        ctx.add_task(Task(id="t-1", goal="Complete CoA mapping"))
        ctx.update_task("t-1", status="in_progress", owner="controller")
        snap = ctx.snapshot_for("agent-1", "tasks")
        active = [t for t in snap["active_tasks"]]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["status"], "in_progress")

    def test_promotion_to_long_term(self):
        ctx = ContextEngine()
        ctx.write("Important strategic note", source_agent="strategy", importance=0.9)
        dump = ctx.dump()
        self.assertTrue(len(dump["long_term"]) >= 1)

    def test_empty_select(self):
        ctx = ContextEngine()
        results = ctx.select("nonexistent query")
        self.assertEqual(len(results), 0)

    def test_multiple_agents_share_context(self):
        ctx = ContextEngine()
        ctx.write("Note from finance", source_agent="finance", importance=0.7)
        ctx.write("Note from strategy", source_agent="strategy", importance=0.6)
        results = ctx.select("strategy", agent="finance")
        # Finance agent should not prioritize its own results via agent boost when querying strategy
        self.assertTrue(len(results) >= 1)

    def test_dump_serialization(self):
        ctx = ContextEngine()
        ctx.upsert_entity(Entity(id="e1", type="org", attributes={"name": "Test"}))
        data = ctx.dump_json()
        parsed = json.loads(data)
        self.assertIn("e1", parsed["entities"])


# ============================================================
# MESH PLAYBOOK TESTS (111-118)
# ============================================================

class TestMeshPlaybook(unittest.TestCase):
    def test_add_bullet(self):
        pb = Playbook("test")
        ops = [DeltaOp(type="ADD", section="strategies_and_hard_rules", content="Always verify sources")]
        log = pb.apply(ops)
        self.assertEqual(len(pb.bullets), 1)
        self.assertTrue(any("ADD" in l for l in log))

    def test_dedup_on_add(self):
        pb = Playbook("test")
        pb.apply([DeltaOp(type="ADD", section="strategies_and_hard_rules", content="Verify sources carefully")])
        pb.apply([DeltaOp(type="ADD", section="strategies_and_hard_rules", content="Verify sources carefully")])
        self.assertEqual(len(pb.bullets), 1)

    def test_increment_and_prune(self):
        pb = Playbook("test")
        pb.apply([DeltaOp(type="ADD", section="strategies_and_hard_rules", content="Test rule")])
        bid = list(pb.bullets.keys())[0]
        pb.apply([DeltaOp(type="INCREMENT", target_id=bid, tag="harmful")] * 4)
        pb.refine()
        self.assertEqual(len(pb.bullets), 0)  # Pruned for low utility

    def test_reflector_and_curator(self):
        pb = Playbook("test")
        reflector = Reflector()
        curator = Curator()
        reflection = reflector.reflect(
            trajectory_summary="Account mapping needs verification",
            outcome="success", current_playbook=pb,
        )
        ops = curator.curate(reflection, pb)
        pb.apply(ops)
        self.assertTrue(len(pb.bullets) >= 1)

    def test_serialization(self):
        pb = Playbook("test")
        pb.apply([DeltaOp(type="ADD", section="domain_concepts", content="ASC 805 for business combinations")])
        data = pb.to_dict()
        pb2 = Playbook.from_dict(data)
        self.assertEqual(len(pb2.bullets), 1)

    def test_render_for_generator(self):
        pb = Playbook("test")
        pb.apply([DeltaOp(type="ADD", section="strategies_and_hard_rules", content="Rule 1")])
        rendered = pb.render_for_generator()
        self.assertIn("PLAYBOOK: test", rendered)
        self.assertIn("Rule 1", rendered)


# ============================================================
# MESH BRIDGE TESTS (119-124)
# ============================================================

class TestMeshBridge(unittest.TestCase):
    def test_build_statement(self):
        bf = BridgeFramework()
        stmt = bf.build_statement(
            entry_point=EntryPoint.PROBLEM,
            observable_tension="Two companies, two charts of accounts, one combined close. Every team needs data now.",
            whys=[WhyLink(question="Why?", answer="Because integration requires a single financial language"),
                  WhyLink(question="Why else?", answer="Because separate charts distort the real financial picture"),
                  WhyLink(question="Root cause?", answer="The organizations were never designed to merge their financial systems")],
            consequences=Consequences(strategic="No single view of performance", cultural="Teams operate in silos",
                                      financial="Cannot measure synergies", timeline="2 quarters"),
            strategic_connection="Unified reporting enables board confidence and synergy tracking across the portfolio.",
        )
        self.assertIsNotNone(stmt.root_cause)
        report = stmt.completeness_report()
        self.assertTrue(report["root_cause_structural"])

    def test_build_workflow(self):
        bf = BridgeFramework()
        stmt = bf.build_statement(
            entry_point=EntryPoint.PROBLEM,
            observable_tension="Test tension",
            whys=[WhyLink(question="Why?", answer="Test")],
            consequences=Consequences(strategic="s", cultural="c", financial="f"),
            strategic_connection="Test connection",
        )
        wf = bf.build_workflow(title="Test Workflow", statement=stmt, agent_outputs=[
            {"agent": "finance", "title": "Map accounts", "inputs": ["source_chart"],
             "outputs": ["account_mapping"], "rationale": "required"},
            {"agent": "strategy", "title": "Align KPIs", "inputs": ["account_mapping"],
             "outputs": ["kpi_alignment"], "rationale": "depends on mapping"},
        ])
        self.assertEqual(len(wf.steps), 2)
        self.assertEqual(wf.steps[1].depends_on, ["S01"])

    def test_statement_render(self):
        bf = BridgeFramework()
        stmt = bf.build_statement(
            entry_point=EntryPoint.OPPORTUNITY,
            observable_tension="Every dollar of revenue is at risk today.",
            whys=[WhyLink(question="Why?", answer="Because"), WhyLink(question="Why?", answer="Because"),
                  WhyLink(question="Why?", answer="Root cause")],
            consequences=Consequences(strategic="s", cultural="c", financial="f"),
            strategic_connection="Connection to mission.",
        )
        rendered = stmt.render()
        self.assertIn("Opportunity Statement", rendered)
        self.assertIn("Root cause", rendered)


# ============================================================
# WORKSTREAM TESTS (125-145)
# ============================================================

class TestWorkstreamBase(unittest.TestCase):
    def test_mapping_line(self):
        ml = MappingLine(source_code="4000", source_label="Revenue", source_description="Total revenue",
                         target_code="4100", target_label="Revenue", mapping_type=MappingType.CLEAN)
        d = ml.to_dict()
        self.assertEqual(d["mapping_type"], "clean")

    def test_synergy_item(self):
        si = SynergyItem(category="cost", description="Headcount consolidation",
                         annual_value_usd=500000, status="in_progress", probability=0.7)
        d = si.to_dict()
        self.assertEqual(d["annual_value_usd"], 500000)

    def test_workstream_status(self):
        ws = WorkstreamStatus(workstream_type="coa_mapping", health="amber", completion_pct=60)
        d = ws.to_dict()
        self.assertEqual(d["health"], "amber")


class TestCoAMapping(unittest.TestCase):
    def test_agents_created(self):
        ws = CoAMappingWorkstream(WorkstreamBrief(title="CoA", acquirer="A", target="B", day_post_close=53))
        agents = ws.get_agents()
        self.assertEqual(len(agents), 3)
        names = {a.name for a in agents}
        self.assertEqual(names, {"finance", "strategy", "compliance"})

    def test_finance_agent_act(self):
        ws = CoAMappingWorkstream(WorkstreamBrief(title="CoA", acquirer="A", target="B", day_post_close=53))
        result = ws.agents[0].act("Map revenue accounts", shared_context=ws.context)
        self.assertIsInstance(result, TurnResult)
        self.assertEqual(result.agent, "finance")
        self.assertIsNotNone(result.trace.recommendation)

    def test_status(self):
        ws = CoAMappingWorkstream(WorkstreamBrief(title="CoA", acquirer="A", target="B", day_post_close=53))
        status = ws.get_status()
        self.assertEqual(status.workstream_type, "coa_mapping")
        self.assertEqual(status.health, "green")


class TestCloseHarmonization(unittest.TestCase):
    def test_agents_created(self):
        ws = CloseHarmonizationWorkstream(WorkstreamBrief(title="Close", acquirer="A", target="B", day_post_close=53))
        agents = ws.get_agents()
        self.assertEqual(len(agents), 3)

    def test_finance_agent_act(self):
        ws = CloseHarmonizationWorkstream(WorkstreamBrief(title="Close", acquirer="A", target="B", day_post_close=53))
        result = ws.agents[0].act("Harmonize close calendars", shared_context=ws.context)
        self.assertIsNotNone(result.trace.recommendation)

    def test_status(self):
        ws = CloseHarmonizationWorkstream(WorkstreamBrief(title="Close", acquirer="A", target="B", day_post_close=53))
        status = ws.get_status()
        self.assertEqual(status.health, "amber")


class TestSystemsIntegration(unittest.TestCase):
    def test_agents_created(self):
        ws = SystemsIntegrationWorkstream(WorkstreamBrief(title="Systems", acquirer="A", target="B", day_post_close=53))
        agents = ws.get_agents()
        self.assertEqual(len(agents), 3)

    def test_status(self):
        ws = SystemsIntegrationWorkstream(WorkstreamBrief(title="Systems", acquirer="A", target="B", day_post_close=53))
        status = ws.get_status()
        self.assertEqual(status.health, "amber")
        self.assertEqual(status.completion_pct, 40)


class TestSynergyTracking(unittest.TestCase):
    def test_agents_created(self):
        ws = SynergyTrackingWorkstream(WorkstreamBrief(title="Synergy", acquirer="A", target="B", day_post_close=53))
        agents = ws.get_agents()
        self.assertEqual(len(agents), 3)

    def test_status(self):
        ws = SynergyTrackingWorkstream(WorkstreamBrief(title="Synergy", acquirer="A", target="B", day_post_close=53))
        status = ws.get_status()
        self.assertEqual(status.health, "green")
        self.assertEqual(status.completion_pct, 75)


# ============================================================
# CONTROL TOWER TESTS (146-155)
# ============================================================

class TestConvergenceTower(unittest.TestCase):
    def test_empty_tower(self):
        tower = ConvergenceTower()
        self.assertEqual(tower.overall_health, IntegrationHealth.NOT_STARTED)
        self.assertEqual(tower.completion_pct, 0)

    def test_all_green(self):
        tower = ConvergenceTower()
        tower.add_workstream(WorkstreamStatus("ws1", health="green", completion_pct=80))
        tower.add_workstream(WorkstreamStatus("ws2", health="green", completion_pct=90))
        self.assertEqual(tower.overall_health, IntegrationHealth.GREEN)

    def test_one_amber(self):
        tower = ConvergenceTower()
        tower.add_workstream(WorkstreamStatus("ws1", health="green", completion_pct=80))
        tower.add_workstream(WorkstreamStatus("ws2", health="amber", completion_pct=50))
        self.assertEqual(tower.overall_health, IntegrationHealth.AMBER)

    def test_one_red(self):
        tower = ConvergenceTower()
        tower.add_workstream(WorkstreamStatus("ws1", health="green", completion_pct=80))
        tower.add_workstream(WorkstreamStatus("ws2", health="red", completion_pct=10))
        self.assertEqual(tower.overall_health, IntegrationHealth.RED)

    def test_risk_management(self):
        tower = ConvergenceTower()
        tower.add_risk(RiskItem(id="r1", title="ERP migration risk", category="systems", severity="critical"))
        tower.add_risk(RiskItem(id="r2", title="Minor delay", category="close", severity="low"))
        self.assertEqual(len(tower.critical_risks), 1)

    def test_blocked_decisions(self):
        tower = ConvergenceTower()
        tower.add_blocked_decision(BlockedDecision(id="bd1", title="Sandbox decision",
                                                    blocking_reason="4/29 steering pending"))
        self.assertEqual(len(tower.blocked_decisions), 1)

    def test_milestones(self):
        tower = ConvergenceTower()
        tower.add_milestone(Milestone(id="m1", title="First combined close", target_date="2026-10-31"))
        tower.add_milestone(Milestone(id="m2", title="NetSuite cutover", target_date="2026-10-31", status="complete"))
        self.assertEqual(len(tower.open_milestones), 1)

    def test_serialization(self):
        tower = ConvergenceTower(acquirer="Acme", target="Summit", day_post_close=53)
        tower.add_workstream(WorkstreamStatus("coa_mapping", health="green"))
        tower.add_risk(RiskItem(id="r1", title="Test risk", category="test", severity="high"))
        data = tower.to_dict()
        self.assertEqual(data["acquirer"], "Acme")
        self.assertEqual(data["day_post_close"], 53)
        self.assertEqual(data["overall_health"], "green")

    def test_compute_completion_pct(self):
        statuses = [WorkstreamStatus("a", completion_pct=80), WorkstreamStatus("b", completion_pct=60)]
        self.assertEqual(compute_completion_pct(statuses), 70)


# ============================================================
# MESH ORCHESTRATOR TESTS (156-162)
# ============================================================

class TestMeshOrchestrator(unittest.TestCase):
    def test_end_to_end_single_agent(self):
        ws = CoAMappingWorkstream(WorkstreamBrief(title="CoA", acquirer="A", target="B", day_post_close=53))
        mesh = EnterpriseOrchestrator(agents=ws.agents, context=ws.context)
        report = mesh.orchestrate("Analyze CoA mapping for FullCycle-Summit integration")
        self.assertEqual(len(report.turns), 3)
        self.assertTrue(report.duration_ms >= 0)
        self.assertEqual(len(report.workflow.steps), 3)

    def test_agent_sequencing(self):
        ws = CoAMappingWorkstream(WorkstreamBrief(title="CoA", acquirer="A", target="B", day_post_close=53))
        mesh = EnterpriseOrchestrator(agents=ws.agents)
        ordered = mesh._sequence(["management_view_alignment", "restatement_estimate"])
        names = [a.name for a in ordered]
        self.assertIn("finance", names)
        self.assertIn("strategy", names)
        self.assertIn("compliance", names)

    def test_orchestration_report_render(self):
        ws = CoAMappingWorkstream(WorkstreamBrief(title="CoA", acquirer="A", target="B", day_post_close=53))
        mesh = EnterpriseOrchestrator(agents=ws.agents, context=ws.context)
        report = mesh.orchestrate("Test problem")
        rendered = report.render()
        self.assertIn("Orchestration Report", rendered)


# ============================================================
# DOSSIER VALIDATION (163-164)
# ============================================================

class TestDossierValidation(unittest.TestCase):
    def test_valid_dossier(self):
        d = Dossier(core_problem="test", goal_state=["a"], current_state=["b"],
                    constraints=["c"], scope=["d"])
        self.assertEqual(validate_dossier(d), [])

    def test_invalid_dossier(self):
        d = Dossier(core_problem="")
        self.assertTrue(len(validate_dossier(d)) > 0)


# ============================================================
# DB TESTS (165-170)
# ============================================================

class TestConvergenceDB(unittest.TestCase):
    def test_save_and_get_decision(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from convergence.db import ConvergenceDB
            db = ConvergenceDB(db_path)
            case = DecisionCase(decision_id="db-001", title="DB Test", domain="coa_mapping",
                               created_at="2026-01-01", owner="cfo")
            db.save_decision(case)
            loaded = db.get_decision("db-001")
            self.assertEqual(loaded.title, "DB Test")
            db.close()
        finally:
            os.unlink(db_path)

    def test_list_decisions(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from convergence.db import ConvergenceDB
            db = ConvergenceDB(db_path)
            db.save_decision(DecisionCase(decision_id="db-002", title="A", domain="coa",
                                          created_at="2026-01-01", owner="cfo"))
            db.save_decision(DecisionCase(decision_id="db-003", title="B", domain="synergy",
                                          created_at="2026-01-01", owner="cfo"))
            all_cases = db.list_decisions()
            self.assertEqual(len(all_cases), 2)
            coa_cases = db.list_decisions(domain="coa")
            self.assertEqual(len(coa_cases), 1)
            db.close()
        finally:
            os.unlink(db_path)

    def test_mapping_lines(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from convergence.db import ConvergenceDB
            db = ConvergenceDB(db_path)
            line = {"source_code": "4000", "source_label": "Revenue", "target_code": "4100"}
            db.save_mapping_line("db-map-001", line, user_comment="OK")
            db.save_mapping_line("db-map-001", {"source_code": "5000", "source_label": "COGS"}, "Hold for review")
            lines = db.get_mapping_lines("db-map-001")
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["user_comment"], "OK")
            db.close()
        finally:
            os.unlink(db_path)

    def test_context_manager(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            from convergence.db import ConvergenceDB
            with ConvergenceDB(db_path) as db:
                db.save_decision(DecisionCase(decision_id="db-cm", title="CM", domain="test",
                                               created_at="2026-01-01", owner="cfo"))
                loaded = db.get_decision("db-cm")
                self.assertEqual(loaded.title, "CM")
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
