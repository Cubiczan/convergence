"""Synergy tracking workstream."""
from __future__ import annotations

from typing import Any, Dict, List

from convergence.mesh.agent import AgentCapability, ExpansionStep, MeshAgent
from convergence.mesh.protocol import CompressionStep, ConfidenceLevel
from convergence.workstreams.base import BaseWorkstream, WorkstreamBrief, WorkstreamStatus


class SynergyFinanceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="finance",
            capability=AgentCapability(
                domain="synergy_tracking",
                produces=["synergy_pipeline", "value_capture"],
                consumes=["deal_economics", "synergy_targets"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content=f"Build synergy tracking framework: {problem}"),
            ExpansionStep(label="Constraints", content="Synergy claims must be conservative, measurable, and tied to deal economics"),
            ExpansionStep(label="Alternatives", content="Bottom-up tracking by initiative vs. top-down tracking by P&L line impact"),
            ExpansionStep(label="Assumptions", content="Cost synergies are easier to measure than revenue synergies; cross-sell is highest-risk"),
            ExpansionStep(label="Edge cases", content="Synergy realization depends on retention rates, integration pace, and market conditions"),
            ExpansionStep(label="Cross-domain", content="Synergy tracking requires reliable CoA mapping and close harmonization for accuracy"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Build a synergy pipeline with conservative probability-weighted value capture tracking and milestone-based realization gates",
            [CompressionStep(label="Integrate", content="Synergy pipeline with cost, revenue, and cross-sell categories"),
             CompressionStep(label="Commit", content="Pipeline built; tracking framework ready for CFO review")],
            ConfidenceLevel.HIGH,
            "Would change if cross-sell take-rate or retention assumptions deteriorate in early quarters",
            {"synergy_pipeline": "produced", "value_capture": "produced"},
        )


class SynergyStrategyAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="strategy",
            capability=AgentCapability(
                domain="synergy_tracking",
                produces=["synergy_risk_register"],
                consumes=["synergy_pipeline"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content="Identify risks to synergy realization and build mitigation plans"),
            ExpansionStep(label="Constraints", content="Board and PE sponsors expect synergy updates at every steering meeting"),
            ExpansionStep(label="Alternatives", content="Static risk register vs. dynamic risk scoring with automatic flag escalation"),
            ExpansionStep(label="Assumptions", content="Revenue synergies have lower realization rates than cost synergies in software M&A"),
            ExpansionStep(label="Edge cases", content="Customer attrition post-acquisition, sales team turnover, and product integration delays"),
            ExpansionStep(label="Cross-domain", content="Synergy risks compound integration risks and can reshape the deal economics narrative"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Build a synergy risk register ranked by deal economics impact, with flip criteria and mitigation actions",
            [CompressionStep(label="Integrate", content="Risk register with probability-weighted impact scoring"),
             CompressionStep(label="Commit", content="Risk register complete; flip criteria documented for board reporting")],
            ConfidenceLevel.HIGH,
            "Would change if macro conditions deteriorate and revenue synergy assumptions become unachievable",
            {"synergy_risk_register": "produced"},
        )


class SynergyComplianceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="compliance",
            capability=AgentCapability(
                domain="synergy_tracking",
                produces=["synergy_reporting_controls"],
                consumes=["synergy_pipeline", "synergy_risk_register"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content="Establish reporting controls to prevent synergy overstatement"),
            ExpansionStep(label="Constraints", content="Synergy reporting must be auditable; realized synergies must tie to actual P&L impact"),
            ExpansionStep(label="Alternatives", content="Monthly tracking with quarterly reforecast vs. continuous tracking with real-time dashboards"),
            ExpansionStep(label="Assumptions", content="Management bias toward optimistic synergy claims is the primary reporting risk"),
            ExpansionStep(label="Edge cases", content="One-time savings vs. recurring synergies, timing of realization, and allocation across business units"),
            ExpansionStep(label="Cross-domain", content="Synergy reporting controls ensure credibility with board, PE sponsors, and auditors"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Establish synergy reporting controls with clear definitions, realization criteria, and audit trail requirements",
            [CompressionStep(label="Integrate", content="Reporting control framework with realization gates and audit requirements"),
             CompressionStep(label="Commit", content="Controls framework documented and ready for implementation")],
            ConfidenceLevel.HIGH,
            "Would change if auditor disputes synergy realization methodology or timing",
            {"synergy_reporting_controls": "produced"},
        )


class SynergyTrackingWorkstream(BaseWorkstream):
    def __init__(self, brief: WorkstreamBrief) -> None:
        super().__init__(brief)
        self._finance = SynergyFinanceAgent()
        self._strategy = SynergyStrategyAgent()
        self._compliance = SynergyComplianceAgent()
        self.agents = [self._finance, self._strategy, self._compliance]

    def get_agents(self) -> List[MeshAgent]:
        return self.agents

    def run_analysis(self) -> Dict[str, Any]:
        return {"workstream": "synergy_tracking", "brief": self.brief.title,
                "agents": [a.name for a in self.agents]}

    def get_status(self) -> WorkstreamStatus:
        return WorkstreamStatus(workstream_type="synergy_tracking", health="green",
                                completion_pct=75, decisions_locked=1, decisions_open=0,
                                risks_count=2, next_milestone="Q2 synergy reforecast")
