"""EnterpriseOrchestrator — coordinates MeshAgents for integration workstreams."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from convergence.audit.ledger import AuditLedger
from convergence.mesh.agent import MeshAgent, TurnResult
from convergence.mesh.bridge import BridgeFramework, Consequences, EntryPoint, Workflow, WhyLink
from convergence.mesh.context import ContextEngine
from convergence.stigmergy.board import SignalType, StigmergyBoard


@dataclass
class OrchestrationReport:
    problem: str
    turns: List[TurnResult]
    workflow: Workflow
    duration_ms: int
    context_snapshot: Dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        sections = [f"# Orchestration Report", f"**Problem:** {self.problem}",
                    f"**Agents:** {', '.join(t.agent for t in self.turns)}",
                    f"**Duration:** {self.duration_ms}ms", "", "---", ""]
        for t in self.turns:
            sections.append(f"## Agent Turn - {t.agent}")
            sections.append(t.trace.render())
            if t.deltas_applied:
                sections.extend(["", "### Playbook Deltas"] + [f"  - {d}" for d in t.deltas_applied])
            if t.handoff_notes:
                sections.extend(["", "### Handoff Notes"] + [f"  - {n}" for n in t.handoff_notes])
            sections.extend(["", "---", ""])
        sections.append(self.workflow.render())
        return "\n".join(sections)


class EnterpriseOrchestrator:
    """Coordinates MeshAgents for integration workstreams.

    Two coordination substrates are available and composable:

    * ``ledger`` — a signed, append-only audit ledger. Every agent
      recommendation and the final board narrative are written to it, so the
      decision trail is tamper-evident (defaults to an env-keyed ledger).
    * ``board`` — a :class:`StigmergyBoard`. When ``use_stigmergy`` is enabled
      (or a board is passed in), agents coordinate by depositing/reading compact
      typed signals on a shared SQLite board **instead of** relaying full
      transcripts through the LLM. This is additive and non-breaking: the
      topological producer→consumer ordering is unchanged; the board only
      changes *how context flows between turns*.
    """

    def __init__(self, *, agents: List[MeshAgent], context: Optional[ContextEngine] = None,
                 bridge: Optional[BridgeFramework] = None,
                 ledger: Optional[AuditLedger] = None,
                 board: Optional[StigmergyBoard] = None,
                 use_stigmergy: bool = False) -> None:
        self.agents = {a.name: a for a in agents}
        self.context = context or ContextEngine()
        self.bridge = bridge or BridgeFramework()
        # Signed audit ledger — defaults on so every recommendation is signed.
        self.ledger = ledger if ledger is not None else AuditLedger()
        # Stigmergy board — opt-in. Passing a board implies use_stigmergy=True.
        if board is not None:
            self.board: Optional[StigmergyBoard] = board
        elif use_stigmergy:
            self.board = StigmergyBoard(ledger=self.ledger)
        else:
            self.board = None

    def _sequence(self, required_outputs: List[str]) -> List[MeshAgent]:
        producers: Dict[str, MeshAgent] = {}
        for agent in self.agents.values():
            for out in agent.capability.produces:
                producers.setdefault(out, agent)
        ordered: List[MeshAgent] = []
        visited: set = set()

        def visit(agent: MeshAgent) -> None:
            if agent.name in visited:
                return
            visited.add(agent.name)
            for inp in agent.capability.consumes:
                producer = producers.get(inp)
                if producer and producer.name != agent.name:
                    visit(producer)
            ordered.append(agent)

        target_agents = [a for a in self.agents.values() if not required_outputs or
                         any(out in required_outputs for out in a.capability.produces)]
        if not target_agents:
            target_agents = list(self.agents.values())
        for a in target_agents:
            visit(a)
        return ordered

    def orchestrate(self, problem: str, *, entry_point: EntryPoint = EntryPoint.PROBLEM,
                    required_outputs: Optional[List[str]] = None,
                    workflow_title: Optional[str] = None) -> OrchestrationReport:
        start = time.time()
        self.context.record_event(actor="orchestrator", action="intake", object_=problem)
        ordered = self._sequence(required_outputs or [])
        turns: List[TurnResult] = []
        agent_outputs_for_bridge: List[Dict[str, Any]] = []

        for agent in ordered:
            # Stigmergic read: fold the decayed board (peers' compact signals)
            # into shared context instead of relaying full LLM transcripts.
            if self.board is not None:
                self._inject_board_signals(agent.name)

            result = agent.act(problem, shared_context=self.context)
            turns.append(result)
            agent_outputs_for_bridge.append({
                "agent": agent.name,
                "title": result.trace.recommendation[:80],
                "recommendation": result.trace.recommendation,
                "rationale": f"{agent.capability.domain} reasoning (confidence={result.trace.confidence.value})",
                "inputs": agent.capability.consumes,
                "outputs": agent.capability.produces,
            })

            # Stigmergic write: deposit this agent's signals for downstream peers
            # (also mirrored into the signed ledger by the board itself).
            if self.board is not None:
                self._deposit_turn_signals(agent, result)
            # Sign the recommendation into the tamper-evident ledger.
            self._audit_turn(problem, agent, result)

        statement = self._synthesize_statement(problem=problem, entry_point=entry_point, turns=turns)
        workflow = self.bridge.build_workflow(title=workflow_title or f"Response to: {problem[:60]}",
                                              statement=statement, agent_outputs=agent_outputs_for_bridge)
        duration_ms = int((time.time() - start) * 1000)
        self._audit_workflow(problem, workflow, turns)
        return OrchestrationReport(problem=problem, turns=turns, workflow=workflow,
                                   duration_ms=duration_ms, context_snapshot=self.context.dump())

    # --- Stigmergic coordination ----------------------------------------

    def _inject_board_signals(self, agent_name: str) -> None:
        """Write the compact decayed board into shared context for one agent.

        Replaces passing prior agents' full outputs: the agent reads at most a
        dozen strongest live signals (post-decay), not whole transcripts.
        """
        assert self.board is not None
        signals = self.board.context_for(agent_name)
        if not signals:
            return
        lines = [
            f"[{s['type']}] {s['agent']}: {s['content']} (strength={s['strength']})"
            for s in signals
        ]
        self.context.write(
            content="Stigmergy board (decayed peer signals):\n" + "\n".join(lines),
            source_agent="stigmergy_board",
            importance=0.5,
            tags=["stigmergy", "coordination"],
        )

    def _deposit_turn_signals(self, agent: MeshAgent, result: TurnResult) -> None:
        """Deposit an agent's finding, confidence, and any risk flags."""
        assert self.board is not None
        trace = result.trace
        self.board.deposit(
            agent=agent.name, signal_type=SignalType.FINDING,
            key=agent.capability.domain, content=trace.recommendation[:200],
            strength=1.0,
        )
        self.board.deposit(
            agent=agent.name, signal_type=SignalType.CONFIDENCE,
            key=agent.capability.domain, content=trace.confidence.value,
            strength={"high": 1.0, "medium": 0.6, "low": 0.3}[trace.confidence.value],
        )
        for out in agent.capability.produces:
            self.board.deposit(
                agent=agent.name, signal_type=SignalType.DEPENDENCY_NOTE,
                key=out, content=f"{out} now available", strength=1.0,
            )
        for g in trace.grounding:
            if g.risk_flag:
                self.board.deposit(
                    agent=agent.name, signal_type=SignalType.RISK_FLAG,
                    key=agent.capability.domain, content=g.risk_flag, strength=1.0,
                )

    # --- Signed audit ledger --------------------------------------------

    def _audit_turn(self, problem: str, agent: MeshAgent, result: TurnResult) -> None:
        """Write one agent's recommendation to the signed ledger."""
        trace = result.trace
        sources = [
            {"claim": g.claim, "source": g.source, "confidence": g.confidence.value,
             "risk_flag": g.risk_flag}
            for g in trace.grounding
        ]
        self.ledger.append(
            event="recommendation", actor=agent.name,
            inputs={"problem": problem, "domain": agent.capability.domain,
                    "consumes": agent.capability.consumes},
            sources=sources, confidence=trace.confidence.value,
            rationale=trace.recommendation,
        )

    def _audit_workflow(self, problem: str, workflow: Workflow, turns: List[TurnResult]) -> None:
        """Write the final synthesized board narrative to the signed ledger."""
        self.ledger.append(
            event="board_narrative", actor="orchestrator",
            inputs={"problem": problem, "agents": [t.agent for t in turns]},
            sources=[t.agent for t in turns], confidence=None,
            rationale=(workflow.statement.root_cause
                       if getattr(workflow, "statement", None) else workflow.title),
        )

    def _synthesize_statement(self, *, problem: str, entry_point: EntryPoint, turns: List[TurnResult]):
        observable = (f"Today: {problem} - {len(turns)} specialist agent(s) produced recommendations "
                      f"through {sum(len(t.trace.expansion) for t in turns)} expansion steps.")
        whys: List[WhyLink] = []
        for t in turns[:5]:
            if not t.trace.expansion:
                continue
            first = t.trace.expansion[0]
            whys.append(WhyLink(question=f"Why does {t.agent} see this matter?",
                                answer=f"{first.label}: {first.content}"))
        while len(whys) < 3:
            whys.append(WhyLink(question="Why is this still unresolved?",
                                answer="Because the binding constraint has not been named in shared context."))
        hi_conf = sorted(turns, key=lambda t: {"high": 3, "medium": 2, "low": 1}[t.trace.confidence.value],
                         reverse=True)
        financial = hi_conf[0].trace.recommendation if hi_conf else "Impact not yet quantified."
        consequences = Consequences(
            strategic="Mesh loses coherence; agents optimize locally without shared context.",
            cultural="Teams re-solve the same problems in parallel, eroding trust in the system.",
            financial=financial[:200], timeline="2 quarters",
        )
        strategic_connection = ("This connects to the integration mission of producing decisions that are "
                                "both technically rigorous and human-auditable. Every multi-agent output must "
                                "trace back to an observable organizational signal.")
        return self.bridge.build_statement(entry_point=entry_point, observable_tension=observable,
                                            whys=whys, consequences=consequences,
                                            strategic_connection=strategic_connection)
