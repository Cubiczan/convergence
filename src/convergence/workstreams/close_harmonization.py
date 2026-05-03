"""Close harmonization workstream."""
from __future__ import annotations

from typing import Any, Dict, List

from convergence.mesh.agent import AgentCapability, ExpansionStep, MeshAgent
from convergence.mesh.protocol import CompressionStep, ConfidenceLevel
from convergence.workstreams.base import BaseWorkstream, WorkstreamBrief, WorkstreamStatus


class CloseFinanceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="finance",
            capability=AgentCapability(
                domain="close_harmonization",
                produces=["close_calendar", "reconciliation_gaps"],
                consumes=["acquirer_close", "target_close"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content=f"Harmonize close calendars: {problem}"),
            ExpansionStep(label="Constraints", content="Combined close must meet acquirer's existing board reporting deadlines"),
            ExpansionStep(label="Alternatives", content="Full calendar merge vs. staged adoption where target retains interim sub-close"),
            ExpansionStep(label="Assumptions", content="Target's close takes longer due to manual processes; automation will accelerate"),
            ExpansionStep(label="Edge cases", content="Intercompany eliminations and consolidated adjustments need new close steps"),
            ExpansionStep(label="Cross-domain", content="Close quality directly impacts synergy tracking accuracy and audit readiness"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Merge close calendars with a phased approach: adopt acquirer's key dates while adding target-specific reconciliation steps for the first combined close",
            [CompressionStep(label="Integrate", content="Staged close calendar with parallel reconciliation tracks"),
             CompressionStep(label="Commit", content="Harmonized close calendar ready for controller approval")],
            ConfidenceLevel.HIGH,
            "Would change if target's existing close infrastructure cannot support the accelerated timeline",
            {"close_calendar": "produced", "reconciliation_gaps": "produced"},
        )


class CloseStrategyAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="strategy",
            capability=AgentCapability(
                domain="close_harmonization",
                produces=["policy_alignment"],
                consumes=["close_calendar"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content="Identify accounting policy differences that create close risk"),
            ExpansionStep(label="Constraints", content="Material policy differences must be resolved before the first combined close"),
            ExpansionStep(label="Alternatives", content="Adopt acquirer policies wholesale, or create interim dual-reporting with sunset clauses"),
            ExpansionStep(label="Assumptions", content="Revenue recognition and capitalization policies are the most likely areas of divergence"),
            ExpansionStep(label="Edge cases", content="Sales commission capitalization timing, revenue cutoff procedures, and allowance methodology"),
            ExpansionStep(label="Cross-domain", content="Policy harmonization enables clean CoA mapping and reliable synergy measurement"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Document and resolve accounting policy differences, prioritizing revenue recognition and capitalization policies",
            [CompressionStep(label="Integrate", content="Policy alignment register with adoption timeline"),
             CompressionStep(label="Commit", content="Policy differences catalogued and resolution path defined")],
            ConfidenceLevel.HIGH,
            "Would change if material policy differences surface during the first combined close dry-run",
            {"policy_alignment": "produced"},
        )


class CloseComplianceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="compliance",
            capability=AgentCapability(
                domain="close_harmonization",
                produces=["audit_readiness"],
                consumes=["policy_alignment", "reconciliation_gaps"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content="Assess audit readiness of the combined close process"),
            ExpansionStep(label="Constraints", content="Auditor must have clear audit trail from day one of combined reporting"),
            ExpansionStep(label="Alternatives", content="Full audit readiness vs. interim with documented gaps and remediation timeline"),
            ExpansionStep(label="Assumptions", content="Internal controls documentation will need updating for the combined entity"),
            ExpansionStep(label="Edge cases", content="Prior-year comparatives and cut-off procedures are highest audit risk areas"),
            ExpansionStep(label="Cross-domain", content="Audit readiness gaps can block clean close and delay board reporting"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Identify audit readiness gaps in the combined close process and document remediation steps",
            [CompressionStep(label="Integrate", content="Audit readiness assessment with gap register"),
             CompressionStep(label="Commit", content="Audit readiness report ready for CFO and controller review")],
            ConfidenceLevel.MEDIUM,
            "Would change if auditor identifies additional scope areas during interim review",
            {"audit_readiness": "produced"},
        )


class CloseHarmonizationWorkstream(BaseWorkstream):
    def __init__(self, brief: WorkstreamBrief) -> None:
        super().__init__(brief)
        self._finance = CloseFinanceAgent()
        self._strategy = CloseStrategyAgent()
        self._compliance = CloseComplianceAgent()
        self.agents = [self._finance, self._strategy, self._compliance]

    def get_agents(self) -> List[MeshAgent]:
        return self.agents

    def run_analysis(self) -> Dict[str, Any]:
        return {"workstream": "close_harmonization", "brief": self.brief.title,
                "agents": [a.name for a in self.agents]}

    def get_status(self) -> WorkstreamStatus:
        return WorkstreamStatus(workstream_type="close_harmonization", health="amber",
                                completion_pct=60, decisions_locked=0, decisions_open=2,
                                risks_count=3, next_milestone="Policy alignment sign-off")
