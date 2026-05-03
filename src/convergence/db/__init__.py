"""SQLite-backed persistence for decisions, workstreams, and Convergence state."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from convergence.chp.models import DecisionCase


class ConvergenceDB:
    """SQLite database for Convergence persistence.

    Stores decision cases, workstream state, and Convergence snapshots.
    Runs without any external database server — perfect for DO App Platform
    local storage. Upgrade to Managed PostgreSQL for production via the
    convergence[postgres] extra.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS decisions (
        decision_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        domain TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'EXPLORING',
        owner TEXT NOT NULL,
        created_at TEXT NOT NULL,
        case_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS workstream_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workstream_type TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS convergence_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS mapping_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id TEXT NOT NULL,
        line_json TEXT NOT NULL,
        user_comment TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY (decision_id) REFERENCES decisions(decision_id)
    );

    CREATE INDEX IF NOT EXISTS idx_decisions_domain ON decisions(domain);
    CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
    CREATE INDEX IF NOT EXISTS idx_mapping_decision ON mapping_lines(decision_id);
    """

    def __init__(self, db_path: str | Path = "convergence.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)

    def save_decision(self, case: DecisionCase) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO decisions (decision_id, title, domain, status, owner, created_at, case_json, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case.decision_id, case.title, case.domain, case.status.value,
             case.owner, case.created_at, json.dumps(case.to_dict()), time.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        self._conn.commit()

    def get_decision(self, decision_id: str) -> Optional[DecisionCase]:
        row = self._conn.execute("SELECT case_json FROM decisions WHERE decision_id = ?", (decision_id,)).fetchone()
        if not row:
            return None
        return DecisionCase.from_dict(json.loads(row["case_json"]))

    def list_decisions(self, domain: Optional[str] = None, status: Optional[str] = None) -> List[DecisionCase]:
        query = "SELECT case_json FROM decisions WHERE 1=1"
        params: list = []
        if domain:
            query += " AND domain = ?"
            params.append(domain)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [DecisionCase.from_dict(json.loads(r["case_json"])) for r in rows]

    def save_workstream_snapshot(self, workstream_type: str, snapshot: Dict[str, Any]) -> int:
        cursor = self._conn.execute(
            "INSERT INTO workstream_snapshots (workstream_type, snapshot_json, created_at) VALUES (?, ?, ?)",
            (workstream_type, json.dumps(snapshot), time.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        self._conn.commit()
        return cursor.lastrowid

    def save_convergence_snapshot(self, snapshot: Dict[str, Any]) -> int:
        cursor = self._conn.execute(
            "INSERT INTO convergence_snapshots (snapshot_json, created_at) VALUES (?, ?)",
            (json.dumps(snapshot), time.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        self._conn.commit()
        return cursor.lastrowid

    def save_mapping_line(self, decision_id: str, line_json: Dict[str, Any],
                          user_comment: str = "") -> int:
        cursor = self._conn.execute(
            "INSERT INTO mapping_lines (decision_id, line_json, user_comment, created_at) VALUES (?, ?, ?, ?)",
            (decision_id, json.dumps(line_json), user_comment, time.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_mapping_lines(self, decision_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT line_json, user_comment FROM mapping_lines WHERE decision_id = ? ORDER BY id",
            (decision_id,),
        ).fetchall()
        result = []
        for r in rows:
            line = json.loads(r["line_json"])
            line["user_comment"] = r["user_comment"]
            result.append(line)
        return result

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
