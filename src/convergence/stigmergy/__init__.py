"""Stigmergy — shared-state, zero-token coordination for the agent mesh.

Agents deposit compact typed signals (finding, risk-flag, dependency-note,
confidence) onto a shared board with exponential decay and TTL expiry, and
read the board as context instead of receiving full transcripts of other
agents' outputs. Board writes and orchestrator decisions are recorded in an
HMAC-SHA256-signed append-only JSONL audit ledger (``convergence.audit``).

Pattern adapted from cubiczan-swarm-pack (scent-field pheromones) and
swarmfi-preps (persistent SQLite stigmergy board).
"""
from convergence.audit.ledger import AuditLedger, default_ledger_path
from convergence.stigmergy.board import (
    GC_THRESHOLD,
    SIGNAL_HALF_LIVES,
    Signal,
    SignalType,
    StigmergyBoard,
)

__all__ = [
    "AuditLedger",
    "GC_THRESHOLD",
    "SIGNAL_HALF_LIVES",
    "Signal",
    "SignalType",
    "StigmergyBoard",
    "default_ledger_path",
]
