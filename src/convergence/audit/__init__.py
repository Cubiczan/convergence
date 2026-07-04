"""Signed audit ledger for Convergence.

Every board narrative / recommendation is written to an HMAC-SHA256-signed,
append-only JSONL ledger so the post-merger-integration reasoning trail is
tamper-evident. Scheme extracted from the signed-ledger donors (cleanmandate,
swarmfi-executor, glacier-edge-arm, compliance-as-code-agent) and strengthened
with per-record signature chaining (each line signs the prior line's signature).
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
