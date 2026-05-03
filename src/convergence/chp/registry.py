"""Registry for CHP decision cases — JSON + optional SQLite persistence."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from convergence.chp.models import DecisionCase, SessionStatus


@dataclass
class DecisionRegistry:
    _cases: Dict[str, DecisionCase] = field(default_factory=dict)

    def add(self, case: DecisionCase) -> None:
        self._cases[case.decision_id] = case

    def get(self, decision_id: str) -> Optional[DecisionCase]:
        return self._cases.get(decision_id)

    def remove(self, decision_id: str) -> bool:
        if decision_id in self._cases:
            del self._cases[decision_id]
            return True
        return False

    def find_related(self, text: str) -> List[DecisionCase]:
        query = text.lower()
        hits: List[DecisionCase] = []
        for case in self._cases.values():
            if query in case.title.lower() or query in case.domain.lower():
                hits.append(case)
                continue
            if case.dossier and case.dossier.core_problem and query in case.dossier.core_problem.lower():
                hits.append(case)
        return hits

    def find_by_domain(self, domain: str) -> List[DecisionCase]:
        return [c for c in self._cases.values() if c.domain.lower() == domain.lower()]

    def find_by_status(self, status: SessionStatus) -> List[DecisionCase]:
        return [c for c in self._cases.values() if c.status == status]

    def locked(self) -> List[DecisionCase]:
        return self.find_by_status(SessionStatus.LOCKED)

    def all(self) -> List[DecisionCase]:
        return list(self._cases.values())

    def count(self) -> int:
        return len(self._cases)

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {decision_id: case.to_dict() for decision_id, case in self._cases.items()}
        target.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "DecisionRegistry":
        target = Path(path)
        if not target.exists():
            return cls()
        raw = json.loads(target.read_text())
        registry = cls()
        for decision_id, case_data in raw.items():
            registry._cases[decision_id] = DecisionCase.from_dict(case_data)
        return registry
