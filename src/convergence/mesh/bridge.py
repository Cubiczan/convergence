"""Bridge Framework — translates multi-agent outputs into statements and workflows."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class EntryPoint(str, Enum):
    PROBLEM = "problem"
    OPPORTUNITY = "opportunity"
    SITUATION = "situation"


@dataclass
class WhyLink:
    question: str
    answer: str


@dataclass
class Consequences:
    strategic: str
    cultural: str
    financial: str
    timeline: str = "6 months"


@dataclass
class Statement:
    entry_point: EntryPoint
    observable_tension: str
    whys: List[WhyLink]
    root_cause: str
    consequences: Consequences
    strategic_connection: str

    def render(self) -> str:
        lines = [f"## {self.entry_point.value.title()} Statement", "", "### Observable Tension",
                 self.observable_tension, "", "### 5 Whys"]
        for i, w in enumerate(self.whys, 1):
            lines.append(f"{i}. **{w.question}** -> {w.answer}")
        lines.extend(["", "### Root Cause", self.root_cause, "",
                      f"### Consequences if Unaddressed ({self.consequences.timeline})",
                      f"- **Strategic:** {self.consequences.strategic}",
                      f"- **Cultural:** {self.consequences.cultural}",
                      f"- **Financial:** {self.consequences.financial}", "",
                      "### Strategic Connection", self.strategic_connection])
        return "\n".join(lines)

    def completeness_report(self) -> Dict[str, bool]:
        return {
            "initiating_moment_specific": bool(self.observable_tension) and len(self.observable_tension) > 20,
            "root_cause_structural": len(self.whys) >= 3 and bool(self.root_cause),
            "consequences_visible": all((self.consequences.strategic, self.consequences.cultural, self.consequences.financial)),
            "strategic_link": len(self.strategic_connection) > 15,
            "vivid_language": any(w in self.observable_tension.lower() for w in ("each", "every", "already", "now", "today")) or "$" in self.observable_tension,
        }


@dataclass
class WorkflowStep:
    id: str
    title: str
    owner: str
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    rationale: str = ""

    def render(self) -> str:
        deps = f" (after {', '.join(self.depends_on)})" if self.depends_on else ""
        return f"- **{self.id}** [{self.owner}] {self.title}{deps}\n    inputs: {self.inputs or '-'}\n    outputs: {self.outputs or '-'}\n    rationale: {self.rationale}"


@dataclass
class Workflow:
    title: str
    statement: Statement
    steps: List[WorkflowStep]

    def render(self) -> str:
        lines = [f"# Workflow: {self.title}", "", self.statement.render(), "", "## Executable Steps"]
        for step in self.steps:
            lines.append(step.render())
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "statement": {"entry_point": self.statement.entry_point.value,
                          "observable_tension": self.statement.observable_tension,
                          "whys": [{"q": w.question, "a": w.answer} for w in self.statement.whys],
                          "root_cause": self.statement.root_cause,
                          "consequences": {"strategic": self.statement.consequences.strategic,
                                           "cultural": self.statement.consequences.cultural,
                                           "financial": self.statement.consequences.financial,
                                           "timeline": self.statement.consequences.timeline},
                          "strategic_connection": self.statement.strategic_connection},
            "steps": [{"id": s.id, "title": s.title, "owner": s.owner, "inputs": s.inputs,
                       "outputs": s.outputs, "depends_on": s.depends_on, "rationale": s.rationale}
                      for s in self.steps],
        }


class BridgeFramework:
    def build_statement(self, *, entry_point: EntryPoint, observable_tension: str,
                        whys: List[WhyLink], consequences: Consequences,
                        strategic_connection: str) -> Statement:
        root_cause = whys[-1].answer if whys else "Root cause not yet explored."
        return Statement(entry_point=entry_point, observable_tension=observable_tension,
                         whys=whys, root_cause=root_cause, consequences=consequences,
                         strategic_connection=strategic_connection)

    def build_workflow(self, *, title: str, statement: Statement,
                       agent_outputs: List[Dict[str, Any]]) -> Workflow:
        steps: List[WorkflowStep] = []
        produced: Dict[str, str] = {}
        for i, out in enumerate(agent_outputs, 1):
            sid = f"S{i:02d}"
            inputs = list(out.get("inputs", []))
            outputs = list(out.get("outputs", []))
            depends = sorted({produced[inp] for inp in inputs if inp in produced})
            steps.append(WorkflowStep(id=sid, title=out.get("title", out.get("recommendation", "step")),
                                      owner=out["agent"], inputs=inputs, outputs=outputs,
                                      depends_on=depends, rationale=out.get("rationale", "")))
            for o in outputs:
                produced[o] = sid
        return Workflow(title=title, statement=statement, steps=steps)
