"""Compatibility shim — the canonical audit ledger now lives in
``convergence.audit.ledger``.

The stigmergy board records its signal deposits into the same signed,
append-only JSONL ledger used for orchestrator decisions, so board writes and
recommendations share one tamper-evident chain. Import from
``convergence.audit`` in new code; this module re-exports for back-compat.
"""
from convergence.audit.ledger import (
    KEY_ENV_VAR,
    AuditLedger,
    canonical_json,
    compute_sig,
    default_ledger_path,
    resolve_key,
)

__all__ = [
    "AuditLedger",
    "KEY_ENV_VAR",
    "canonical_json",
    "compute_sig",
    "default_ledger_path",
    "resolve_key",
]
