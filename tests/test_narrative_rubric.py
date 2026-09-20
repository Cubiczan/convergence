"""Row 35 rubric chain: the synthesized board narrative is graded, not trusted."""

from __future__ import annotations

import unittest

from convergence.mesh.agent import TurnResult
from convergence.mesh.bridge import Consequences, EntryPoint, Statement, WhyLink
from convergence.mesh.protocol import (
    ConfidenceLevel,
    GroundingCheck,
    ProblemType,
    ReasoningTrace,
)
from convergence.mesh.rubric import (
    PADDING_WHY_ANSWER as PADDING,
    RubricResult,
    evaluate_narrative,
)


def _turn(agent: str, *, confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
          grounding: list[GroundingCheck] | None = None) -> TurnResult:
    trace = ReasoningTrace(problem="p", problem_type=ProblemType.STRATEGIC,
                           classification_rationale="r")
    trace.confidence = confidence
    trace.grounding = grounding or []
    return TurnResult(agent=agent, trace=trace, deltas_applied=[], outputs={})


def _statement(*, whys: list[WhyLink], root_cause: str) -> Statement:
    return Statement(
        entry_point=EntryPoint.PROBLEM,
        observable_tension="today",
        whys=whys,
        root_cause=root_cause,
        consequences=Consequences(strategic="s", cultural="c", financial="f"),
        strategic_connection="sc",
    )


class TestNarrativeRubric(unittest.TestCase):
    def test_full_quality_narrative_clears(self):
        whys = [WhyLink(question=f"why {i}", answer=f"because {i}") for i in range(3)]
        statement = _statement(whys=whys, root_cause="because 2")
        turns = [
            _turn("finance", confidence=ConfidenceLevel.HIGH,
                  grounding=[GroundingCheck(claim="c1", source="S-1", confidence=ConfidenceLevel.HIGH)]),
            _turn("strategy", confidence=ConfidenceLevel.MEDIUM,
                  grounding=[GroundingCheck(claim="c2", source="S-2", confidence=ConfidenceLevel.MEDIUM)]),
        ]
        result = evaluate_narrative(statement=statement, turns=turns)
        self.assertIsInstance(result, RubricResult)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.status, "CLEAR")
        self.assertTrue(all(f.passed for f in result.findings))

    def test_placeholder_padded_whys_fail_and_score_drops(self):
        # The synthesizer pads short why-chains with the placeholder answer;
        # a narrative whose root cause or why-links are placeholder text is
        # NOT fully resolved and must not read as a clean 100.
        whys = [
            WhyLink(question="why 1", answer="because 1"),
            WhyLink(question="why 2", answer=PADDING),
            WhyLink(question="why 3", answer=PADDING),
        ]
        statement = _statement(whys=whys, root_cause=PADDING)
        turns = [_turn("finance", confidence=ConfidenceLevel.HIGH)]
        result = evaluate_narrative(statement=statement, turns=turns)
        root_f = next(f for f in result.findings if f.criterion == "root_cause_named")
        why_f = next(f for f in result.findings if f.criterion == "why_links_resolved")
        self.assertFalse(root_f.passed)
        self.assertFalse(why_f.passed)
        self.assertLess(result.score, 100)
        self.assertEqual(result.status, "REQUIRES_HUMAN_VERIFICATION")

    def test_unsourced_grounding_is_flagged(self):
        whys = [WhyLink(question=f"why {i}", answer=f"because {i}") for i in range(3)]
        statement = _statement(whys=whys, root_cause="because 2")
        turns = [
            _turn("finance",
                  grounding=[GroundingCheck(claim="c1", source="", confidence=ConfidenceLevel.HIGH)]),
        ]
        result = evaluate_narrative(statement=statement, turns=turns)
        grounding_f = next(f for f in result.findings if f.criterion == "grounding_sourced")
        self.assertFalse(grounding_f.passed)

    def test_no_high_confidence_turn_is_flagged(self):
        whys = [WhyLink(question=f"why {i}", answer=f"because {i}") for i in range(3)]
        statement = _statement(whys=whys, root_cause="because 2")
        turns = [_turn("finance", confidence=ConfidenceLevel.LOW)]
        result = evaluate_narrative(statement=statement, turns=turns)
        conf_f = next(f for f in result.findings if f.criterion == "high_confidence_contribution")
        self.assertFalse(conf_f.passed)

    def test_weights_sum_to_a_full_score(self):
        from convergence.mesh.rubric import CRITERION_WEIGHTS

        self.assertEqual(sum(CRITERION_WEIGHTS.values()), 100)


if __name__ == "__main__":
    unittest.main()
