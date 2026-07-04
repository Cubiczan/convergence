"""HMAC-SHA256-signed, append-only JSONL audit ledger.

Every board narrative / recommendation the Convergence mesh emits is written
here as one signed JSONL line so the post-merger-integration reasoning trail is
tamper-evident and defensible to an audit committee, external auditor, or
regulator.

Scheme (extracted from the signed-ledger donors — cleanmandate,
swarmfi-executor, glacier-edge-arm, compliance-as-code-agent):

    * One JSON record per line, append-only, never rewritten.
    * The signature for a record is ``HMAC-SHA256(key, canonical_json(record) + prev_sig)``
      where ``canonical_json`` is the deterministic (sorted-key, tight-separator)
      encoding of every field *except* ``sig`` itself, and ``prev_sig`` is the
      signature of the immediately preceding line (``""`` for the genesis line).
    * Because each line folds in the prior signature, deletion, reordering, or
      in-place edits break the chain from the first tampered record onward —
      ``verify()`` reports whether the chain is intact and the index of the
      first tampered record.

Record shape::

    {ts, event, actor, inputs, sources, confidence?, rationale?, prev_sig, sig}

The signing key is read from ``AUDIT_LEDGER_KEY`` with a well-known test
default so the offline demo/tests run without configuration. In production set
``AUDIT_LEDGER_KEY`` to a secret and keep it out of the repo.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

# Env var that holds the signing key; TEST_DEFAULT keeps the offline demo/tests
# runnable without configuration. Override AUDIT_LEDGER_KEY in production.
KEY_ENV_VAR = "AUDIT_LEDGER_KEY"
TEST_DEFAULT_KEY = "convergence-test-audit-key"  # noqa: S105 — deliberate test default

GENESIS_PREV_SIG = ""


def resolve_key(explicit: Optional[str] = None) -> str:
    """Signing key: explicit arg > ``AUDIT_LEDGER_KEY`` env > test default."""
    return explicit or os.environ.get(KEY_ENV_VAR) or TEST_DEFAULT_KEY


def canonical_json(record: Dict[str, Any]) -> str:
    """Deterministic JSON used as the signed payload (``sig`` excluded)."""
    payload = {k: v for k, v in record.items() if k != "sig"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_sig(key: str, record: Dict[str, Any], prev_sig: str) -> str:
    """``HMAC-SHA256(key, canonical_json(record) + prev_sig)`` as hex."""
    message = (canonical_json(record) + prev_sig).encode("utf-8")
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def default_ledger_path(root: Path | str = ".") -> Path:
    return Path(root) / ".convergence" / "audit.jsonl"


class AuditLedger:
    """Append-only, signature-chained JSONL audit ledger.

    Thread-safe: a process-level lock serializes reads of the tail signature and
    appends so concurrent agents can log to the same ledger safely.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        key: Optional[str] = None,
    ) -> None:
        self.path = Path(path) if path is not None else default_ledger_path()
        self.key = resolve_key(key)
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------
    def append(
        self,
        *,
        event: str,
        actor: str,
        inputs: Any,
        sources: Any,
        confidence: Optional[str] = None,
        rationale: Optional[str] = None,
        ts: Optional[str] = None,
    ) -> str:
        """Sign and append one record; return its signature.

        The record's ``prev_sig`` is the signature of the current last line, so
        each line cryptographically commits to the entire history before it.
        """
        record: Dict[str, Any] = {
            "ts": ts or datetime.now(timezone.utc).isoformat(),
            "event": event,
            "actor": actor,
            "inputs": inputs,
            "sources": sources,
        }
        if confidence is not None:
            record["confidence"] = confidence
        if rationale is not None:
            record["rationale"] = rationale

        with self._lock:
            prev_sig = self._last_sig_unlocked()
            record["prev_sig"] = prev_sig
            record["sig"] = compute_sig(self.key, record, prev_sig)
            self._append_line_unlocked(record)
        return record["sig"]

    def append_record(self, record: Dict[str, Any]) -> str:
        """Append a pre-shaped record dict (``event``/``actor`` required)."""
        return self.append(
            event=record["event"],
            actor=record["actor"],
            inputs=record.get("inputs"),
            sources=record.get("sources"),
            confidence=record.get("confidence"),
            rationale=record.get("rationale"),
            ts=record.get("ts"),
        )

    # ------------------------------------------------------------------
    # Read / verify path
    # ------------------------------------------------------------------
    def read_all(self) -> List[Dict[str, Any]]:
        return self.read_records(self.path)

    @staticmethod
    def read_records(path: Path | str) -> List[Dict[str, Any]]:
        p = Path(path)
        if not p.exists():
            return []
        records: List[Dict[str, Any]] = []
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def verify(self, path: Path | str | None = None) -> Tuple[bool, Optional[int]]:
        """Walk the chain; return ``(intact, first_tampered_index)``.

        ``intact`` is True only if every line's signature recomputes and every
        line's ``prev_sig`` matches the previous line's ``sig``. On failure,
        ``first_tampered_index`` is the 0-based index of the earliest bad line;
        it is ``None`` when the ledger is intact (or empty).
        """
        target = Path(path) if path is not None else self.path
        try:
            records = self.read_records(target)
        except (json.JSONDecodeError, OSError):
            return False, 0

        expected_prev = GENESIS_PREV_SIG
        for i, rec in enumerate(records):
            stored_sig = rec.get("sig", "")
            stored_prev = rec.get("prev_sig", "")
            # Chain link: this record must point at the prior record's signature.
            if stored_prev != expected_prev:
                return False, i
            # Content integrity: recompute the signature over the record body.
            recomputed = compute_sig(self.key, rec, stored_prev)
            if not hmac.compare_digest(recomputed, stored_sig):
                return False, i
            expected_prev = stored_sig
        return True, None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _last_sig_unlocked(self) -> str:
        if not self.path.exists():
            return GENESIS_PREV_SIG
        last = ""
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    last = line
        if not last:
            return GENESIS_PREV_SIG
        try:
            return json.loads(last).get("sig", GENESIS_PREV_SIG)
        except json.JSONDecodeError:
            return GENESIS_PREV_SIG

    def _append_line_unlocked(self, record: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
