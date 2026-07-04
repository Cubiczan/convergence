"""Stigmergy board — SQLite-backed shared signal environment.

Agents coordinate through the environment (stigmergy) instead of through
inter-agent transcripts: each agent deposits compact typed signals after its
turn, and downstream agents read the decayed board as context. Reads and
writes are pure arithmetic + SQL — zero LLM calls for coordination.

Decay follows the exponential pheromone model from cubiczan-swarm-pack:
    current = strength * exp(-lambda * elapsed), lambda = ln(2) / half_life
Signals additionally carry a hard TTL (expires_at semantics) after which they
are ignored and garbage-collected regardless of remaining strength.
"""
from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from convergence.audit.ledger import AuditLedger


class SignalType(str, Enum):
    """Typed signals agents deposit on the board."""

    FINDING = "finding"                  # A produced insight/recommendation
    RISK_FLAG = "risk_flag"              # A risk another agent should see
    DEPENDENCY_NOTE = "dependency_note"  # An output is now available
    CONFIDENCE = "confidence"            # Agent's confidence in its own work


# Half-lives (seconds) for exponential decay, per signal type.
SIGNAL_HALF_LIVES: Dict[SignalType, float] = {
    SignalType.FINDING: 3600.0,          # 1 hour
    SignalType.RISK_FLAG: 7200.0,        # 2 hours — risks linger longest
    SignalType.DEPENDENCY_NOTE: 1800.0,  # 30 minutes
    SignalType.CONFIDENCE: 900.0,        # 15 minutes — freshness matters
}

# Decay constants: lambda = ln(2) / half_life
DECAY_CONSTANTS: Dict[SignalType, float] = {
    st: math.log(2) / hl for st, hl in SIGNAL_HALF_LIVES.items()
}

# Default TTL per type (seconds) — hard expiry independent of decay.
DEFAULT_TTLS: Dict[SignalType, float] = {
    st: hl * 4 for st, hl in SIGNAL_HALF_LIVES.items()
}

# Signals whose decayed strength falls below this are treated as expired.
GC_THRESHOLD = 0.05


@dataclass
class Signal:
    """A single typed signal deposited on the board."""

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    signal_type: SignalType = SignalType.FINDING
    key: str = ""
    content: str = ""
    strength: float = 1.0
    deposited_at: float = field(default_factory=time.time)
    ttl_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.ttl_seconds <= 0:
            self.ttl_seconds = DEFAULT_TTLS[self.signal_type]

    def current_strength(self, now: Optional[float] = None) -> float:
        """Decayed strength at ``now`` (pure arithmetic, zero LLM calls)."""
        now = time.time() if now is None else now
        elapsed = max(0.0, now - self.deposited_at)
        decay = DECAY_CONSTANTS[self.signal_type]
        return self.strength * math.exp(-decay * elapsed)

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        if now >= self.deposited_at + self.ttl_seconds:
            return True
        return self.current_strength(now) < GC_THRESHOLD

    def to_compact(self, now: Optional[float] = None) -> Dict[str, Any]:
        """Compact representation injected into agent context (small prompt)."""
        return {
            "agent": self.agent,
            "type": self.signal_type.value,
            "key": self.key,
            "content": self.content,
            "strength": round(self.current_strength(now), 3),
        }


class StigmergyBoard:
    """Shared, SQLite-backed signal board read/written by all mesh agents.

    Replaces full-transcript context passing: downstream agents receive the
    compact decayed board instead of prior agents' complete outputs.
    """

    def __init__(self, db_path: str = ":memory:", *,
                 ledger: Optional[AuditLedger] = None) -> None:
        self.db_path = db_path
        self.ledger = ledger
        self._lock = threading.RLock()
        # Single persistent connection (required for :memory: databases).
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS stigmergy_signals (
                    signal_id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    key TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    strength REAL NOT NULL DEFAULT 1.0,
                    deposited_at REAL NOT NULL,
                    ttl_seconds REAL NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_stig_type
                    ON stigmergy_signals(signal_type);
                CREATE INDEX IF NOT EXISTS idx_stig_agent
                    ON stigmergy_signals(agent);
                CREATE INDEX IF NOT EXISTS idx_stig_key
                    ON stigmergy_signals(key);
                """
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------
    def deposit(self, *, agent: str, signal_type: SignalType, key: str = "",
                content: str = "", strength: float = 1.0,
                ttl_seconds: Optional[float] = None,
                metadata: Optional[Dict[str, Any]] = None) -> Signal:
        """Deposit a typed signal onto the board (and audit-log the write)."""
        signal = Signal(
            agent=agent,
            signal_type=signal_type,
            key=key,
            content=content,
            strength=max(0.0, strength),
            ttl_seconds=ttl_seconds or 0.0,
            metadata=metadata or {},
        )
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO stigmergy_signals
                   (signal_id, agent, signal_type, key, content, strength,
                    deposited_at, ttl_seconds, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (signal.signal_id, signal.agent, signal.signal_type.value,
                 signal.key, signal.content, signal.strength,
                 signal.deposited_at, signal.ttl_seconds,
                 json.dumps(signal.metadata)),
            )
            self._conn.commit()
        if self.ledger is not None:
            self.ledger.append(
                event="stigmergy_deposit",
                actor=agent,
                inputs={"signal_id": signal.signal_id,
                        "type": signal.signal_type.value,
                        "key": signal.key,
                        "strength": signal.strength},
                sources=[signal.signal_type.value],
                rationale=signal.content,
            )
        return signal

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------
    def read(self, *, signal_type: Optional[SignalType] = None,
             key: Optional[str] = None, exclude_agent: Optional[str] = None,
             min_strength: float = GC_THRESHOLD,
             now: Optional[float] = None) -> List[Signal]:
        """Read live signals, strongest (post-decay) first."""
        now = time.time() if now is None else now
        query = "SELECT * FROM stigmergy_signals WHERE 1=1"
        params: List[Any] = []
        if signal_type is not None:
            query += " AND signal_type = ?"
            params.append(signal_type.value)
        if key is not None:
            query += " AND key = ?"
            params.append(key)
        if exclude_agent is not None:
            query += " AND agent != ?"
            params.append(exclude_agent)
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        signals: List[Signal] = []
        for row in rows:
            sig = self._row_to_signal(row)
            if sig.is_expired(now) or sig.current_strength(now) < min_strength:
                continue
            signals.append(sig)
        signals.sort(key=lambda s: s.current_strength(now), reverse=True)
        return signals

    def read_strength(self, *, signal_type: SignalType, key: str,
                      now: Optional[float] = None) -> float:
        """Aggregate decayed strength for (type, key) — swarm-pack style."""
        now = time.time() if now is None else now
        return sum(s.current_strength(now)
                   for s in self.read(signal_type=signal_type, key=key, now=now))

    def context_for(self, agent_name: str, *, limit: int = 12,
                    now: Optional[float] = None) -> List[Dict[str, Any]]:
        """Compact board view for one agent's prompt context.

        Excludes the agent's own signals (it already knows them) and returns
        at most ``limit`` of the strongest live signals — this replaces full
        transcripts of other agents' outputs.
        """
        now = time.time() if now is None else now
        signals = self.read(exclude_agent=agent_name, now=now)
        return [s.to_compact(now) for s in signals[:limit]]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------
    def garbage_collect(self, now: Optional[float] = None) -> int:
        """Purge expired signals (past TTL or decayed below GC_THRESHOLD)."""
        now = time.time() if now is None else now
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM stigmergy_signals").fetchall()
            expired = [self._row_to_signal(r).signal_id for r in rows
                       if self._row_to_signal(r).is_expired(now)]
            if expired:
                placeholders = ",".join("?" * len(expired))
                self._conn.execute(
                    f"DELETE FROM stigmergy_signals "
                    f"WHERE signal_id IN ({placeholders})", expired)
                self._conn.commit()
        return len(expired)

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM stigmergy_signals")
            self._conn.commit()

    def count(self) -> int:
        with self._lock:
            (n,) = self._conn.execute(
                "SELECT COUNT(*) FROM stigmergy_signals").fetchone()
        return int(n)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row_to_signal(row: sqlite3.Row) -> Signal:
        return Signal(
            signal_id=row["signal_id"],
            agent=row["agent"],
            signal_type=SignalType(row["signal_type"]),
            key=row["key"],
            content=row["content"],
            strength=row["strength"],
            deposited_at=row["deposited_at"],
            ttl_seconds=row["ttl_seconds"],
            metadata=json.loads(row["metadata"] or "{}"),
        )
