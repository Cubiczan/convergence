"""Chart of Accounts mapping workstream."""
from __future__ import annotations

from typing import Any, Dict, List

from convergence.mesh.agent import AgentCapability, ExpansionStep, MeshAgent
from convergence.mesh.protocol import CompressionStep, ConfidenceLevel
from convergence.mesh.context import ContextEngine
from convergence.workstreams.base import (
    BaseWorkstream,
    MappingLine,
    MappingType,
    WorkstreamBrief,
    WorkstreamStatus,
)


class CoAFinanceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="finance",
            capability=AgentCapability(
                domain="coa_mapping",
                produces=["account_mapping", "kpi_alignment"],
                consumes=["target_chart", "acquirer_chart"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content=f"Translate {problem} from target CoA into acquirer's reporting model"),
            ExpansionStep(label="Constraints", content="Account codes must map to acquirer's management reporting hierarchy without losing granularity"),
            ExpansionStep(label="Alternatives", content="Consider: 1:1 mapping where codes match, judgment mappings where account structures differ, new target lines for accounts with no acquirer equivalent"),
            ExpansionStep(label="Assumptions", content="Assume target's trial balance reflects actual usage; stale accounts may exist but are excluded from active mapping"),
            ExpansionStep(label="Edge cases", content="Deferred revenue, capitalized commissions, contract assets require controller judgment on classification timing"),
            ExpansionStep(label="Cross-domain", content="CoA mapping directly impacts close calendar harmonization and combined management reporting quality"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Map target accounts to acquirer's chart, flagging ambiguous lines for controller review and creating new target lines where no equivalent exists",
            [CompressionStep(label="Integrate", content="Combined mapping approach: clean 1:1, judgment, and new-target categories"),
             CompressionStep(label="Commit", content="First-pass mapping complete; controller review required for all judgment and conflict items")],
            ConfidenceLevel.HIGH,
            "Would change if controller identifies material misclassification in the source trial balance",
            {"account_mapping": "produced", "kpi_alignment": "produced"},
        )


class CoAStrategyAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="strategy",
            capability=AgentCapability(
                domain="coa_mapping",
                produces=["management_view_alignment"],
                consumes=["account_mapping", "kpi_alignment"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content="How does the target's management reporting structure translate into the acquirer's KPI model?"),
            ExpansionStep(label="Constraints", content="Board-level metrics must be comparable from day one of combined reporting"),
            ExpansionStep(label="Alternatives", content="Options: adopt acquirer KPI definitions entirely, create hybrid definitions with dual labels, or grandfather target's KPI approach for one quarter"),
            ExpansionStep(label="Assumptions", content="Management reporting consistency is critical for synergy tracking and board confidence"),
            ExpansionStep(label="Edge cases", content="Customer count definitions, NRR/ARR reconciliation, and gross margin calculation methods may differ"),
            ExpansionStep(label="Cross-domain", content="KPI definition conflicts can distort synergy revenue attribution and close calendar accuracy"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Align management reporting views and KPI definitions, documenting where labels match but calculations differ",
            [CompressionStep(label="Integrate", content="KPI alignment identifies hidden definition conflicts behind matching labels"),
             CompressionStep(label="Commit", content="Management view alignment complete with conflict register")],
            ConfidenceLevel.HIGH,
            "Would change if a material KPI definition conflict is discovered in the first combined close",
            {"management_view_alignment": "produced"},
        )


class CoAComplianceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="compliance",
            capability=AgentCapability(
                domain="coa_mapping",
                produces=["restatement_estimate"],
                consumes=["account_mapping"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content="What balance sheet restatements are required under the mapping, and what is the estimated magnitude?"),
            ExpansionStep(label="Constraints", content="Opening balance sheet restatement must land before audit; ASC 805 purchase price allocation drives timing"),
            ExpansionStep(label="Alternatives", content="Full restatement vs. phased approach with interim dual-reporting"),
            ExpansionStep(label="Assumptions", content="Capitalized software and commissions are the largest restatement items for SaaS acquisitions"),
            ExpansionStep(label="Edge cases", content="Deferred revenue timing differences can create material mismatches in month-one reporting"),
            ExpansionStep(label="Cross-domain", content="Restatement magnitude directly affects synergy tracking and deal economics visibility"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Estimate opening balance sheet restatement: capitalize commissions, contract assets, and capitalized software as ASC 805 adjustments",
            [CompressionStep(label="Integrate", content="Restatement estimate ranges from conservative (minimal capitalization) to aggressive (full ASC 805)"),
             CompressionStep(label="Commit", content="Restatement estimate documented for auditor pre-close review")],
            ConfidenceLevel.MEDIUM,
            "Would change if target's pre-close capitalization policy differs from assumptions",
            {"restatement_estimate": "produced"},
        )


class CoAMappingWorkstream(BaseWorkstream):
    def __init__(self, brief: WorkstreamBrief) -> None:
        super().__init__(brief)
        self._finance = CoAFinanceAgent()
        self._strategy = CoAStrategyAgent()
        self._compliance = CoAComplianceAgent()
        self.agents = [self._finance, self._strategy, self._compliance]

    def get_agents(self) -> List[MeshAgent]:
        return self.agents

    def run_analysis(self) -> Dict[str, Any]:
        return {"workstream": "coa_mapping", "brief": self.brief.title,
                "agents": [a.name for a in self.agents]}

    def get_status(self) -> WorkstreamStatus:
        return WorkstreamStatus(workstream_type="coa_mapping", health="green",
                                completion_pct=100, decisions_locked=0, decisions_open=0,
                                next_milestone="Controller review complete")
