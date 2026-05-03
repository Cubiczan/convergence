"""Systems integration planning workstream."""
from __future__ import annotations

from typing import Any, Dict, List

from convergence.mesh.agent import AgentCapability, ExpansionStep, MeshAgent
from convergence.mesh.protocol import CompressionStep, ConfidenceLevel
from convergence.workstreams.base import BaseWorkstream, WorkstreamBrief, WorkstreamStatus


class SystemsFinanceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="finance",
            capability=AgentCapability(
                domain="systems_integration",
                produces=["system_dependency_map", "cutover_risks"],
                consumes=["acquirer_stack", "target_stack"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content=f"Map system dependencies for: {problem}"),
            ExpansionStep(label="Constraints", content="Systems cutover cannot disrupt ongoing business operations or reporting continuity"),
            ExpansionStep(label="Alternatives", content="Big-bang cutover vs. phased migration by system criticality"),
            ExpansionStep(label="Assumptions", content="Data migration is the highest-risk activity; master data quality determines timeline"),
            ExpansionStep(label="Edge cases", content="Subscription billing migration, CRM deduplication, and payroll system alignment"),
            ExpansionStep(label="Cross-domain", content="System dependencies directly constrain close harmonization and CoA mapping timelines"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Map source-to-target system flows, identify data migration paths, and rank cutover risks by deal economics impact",
            [CompressionStep(label="Integrate", content="System dependency map with critical-path cutover sequence"),
             CompressionStep(label="Commit", content="Dependency map complete; cutover risks ranked and mitigated")],
            ConfidenceLevel.MEDIUM,
            "Would change if data quality assessment reveals material gaps in master data",
            {"system_dependency_map": "produced", "cutover_risks": "produced"},
        )


class SystemsStrategyAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="strategy",
            capability=AgentCapability(
                domain="systems_integration",
                produces=["migration_plan"],
                consumes=["system_dependency_map"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content="Design the phased migration plan from target systems to acquirer stack"),
            ExpansionStep(label="Constraints", content="Must maintain reporting continuity; parallel running period required for critical systems"),
            ExpansionStep(label="Alternatives", content="ERP-first vs. CRM-first vs. billing-first migration sequencing"),
            ExpansionStep(label="Assumptions", content="Target's ERP (Sage Intacct) must migrate to acquirer's NetSuite; API middleware may bridge interim"),
            ExpansionStep(label="Edge cases", content="Historical data retention requirements, regulatory reporting continuity, and third-party integrations"),
            ExpansionStep(label="Cross-domain", content="Migration sequencing constraints close harmonization and synergy tracking accuracy"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Design phased migration plan with parallel running for ERP, CRM, billing, and reporting systems",
            [CompressionStep(label="Integrate", content="Migration plan with phase gates and rollback contingencies"),
             CompressionStep(label="Commit", content="Migration plan documented with cost and timeline estimates")],
            ConfidenceLevel.MEDIUM,
            "Would change if interim API bridge cannot maintain data consistency during parallel running",
            {"migration_plan": "produced"},
        )


class SystemsComplianceAgent(MeshAgent):
    def __init__(self) -> None:
        super().__init__(
            name="compliance",
            capability=AgentCapability(
                domain="systems_integration",
                produces=["security_review"],
                consumes=["system_dependency_map", "migration_plan"],
            ),
        )

    def expand(self, problem: str, context: Dict[str, Any]) -> List[ExpansionStep]:
        return [
            ExpansionStep(label="Reframe", content="Identify security and compliance risks in the systems integration plan"),
            ExpansionStep(label="Constraints", content="SOX compliance must be maintained throughout migration; access controls require immediate unification"),
            ExpansionStep(label="Alternatives", content="Full security audit before migration vs. continuous security monitoring during phased approach"),
            ExpansionStep(label="Assumptions", content="Target's access control maturity may be lower than acquirer's; immediate hardening required"),
            ExpansionStep(label="Edge cases", content="Privileged access during data migration, third-party SaaS sub-processors, and cross-border data transfer"),
            ExpansionStep(label="Cross-domain", content="Security gaps in migration can create regulatory exposure and board-level risk"),
        ]

    def compress(self, problem: str, expansion: List[ExpansionStep], context: Dict[str, Any]
                 ) -> tuple[str, List[CompressionStep], ConfidenceLevel, str, Dict[str, Any]]:
        return (
            "Document security review findings and access control unification plan for the combined entity",
            [CompressionStep(label="Integrate", content="Security assessment with access control consolidation plan"),
             CompressionStep(label="Commit", content="Security review complete; remediation items documented")],
            ConfidenceLevel.HIGH,
            "Would change if penetration testing reveals critical vulnerabilities in target's systems",
            {"security_review": "produced"},
        )


class SystemsIntegrationWorkstream(BaseWorkstream):
    def __init__(self, brief: WorkstreamBrief) -> None:
        super().__init__(brief)
        self._finance = SystemsFinanceAgent()
        self._strategy = SystemsStrategyAgent()
        self._compliance = SystemsComplianceAgent()
        self.agents = [self._finance, self._strategy, self._compliance]

    def get_agents(self) -> List[MeshAgent]:
        return self.agents

    def run_analysis(self) -> Dict[str, Any]:
        return {"workstream": "systems_integration", "brief": self.brief.title,
                "agents": [a.name for a in self.agents]}

    def get_status(self) -> WorkstreamStatus:
        return WorkstreamStatus(workstream_type="systems_integration", health="amber",
                                completion_pct=40, decisions_locked=0, decisions_open=1,
                                risks_count=5, next_milestone="Sandbox provisioning")
