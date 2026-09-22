"""Append-only, hash-chained JSONL audit log (one file per session).

Tamper-evident but NOT yet cryptographically signed: Ed25519 signatures over each entry are
wired in during M1, once common/crypto.py exists (docs/DECISIONS.md ADR-003). The file
format is final -- signatures arrive as an extra field, the hash chaining stays.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

GENESIS_HASH = "0" * 64


class AuditEvent(BaseModel):
    """One audit entry.

    `summary` carries JSON-serializable metadata only -- never decrypted intent/offer
    plaintext (BIGBRAIN_SPEC.md section 7). That is a caller contract, not something this
    model enforces.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    session_id: str
    worker_id: str | None = None
    event_type: str
    summary: dict
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    prev_hash: str
    entry_hash: str = ""


def _canonical_bytes(event: AuditEvent) -> bytes:
    """Canonical JSON of the event, entry_hash excluded -- the input to entry_hash."""
    data = event.model_dump(exclude={"entry_hash"})
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


class AuditLog:
    """Append-only audit trail for one session: <audit_dir>/<session_id>.jsonl."""

    def __init__(self, audit_dir: Path, session_id: str) -> None:
        self.audit_dir = Path(audit_dir)
        self.session_id = session_id
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.audit_dir / f"{session_id}.jsonl"

    def record(self, event_type: str, summary: dict, worker_id: str | None = None) -> AuditEvent:
        """Append one event to the chain and return it with entry_hash set."""
        event = AuditEvent(
            session_id=self.session_id,
            worker_id=worker_id,
            event_type=event_type,
            summary=summary,
            prev_hash=self._last_entry_hash(),
        )
        digest = hashlib.sha256(_canonical_bytes(event)).hexdigest()
        event = event.model_copy(update={"entry_hash": digest})
        with self.path.open("a", encoding="utf-8") as fh:  # opened and closed per record
            fh.write(event.model_dump_json() + "\n")
        return event

    def read_all(self) -> list[AuditEvent]:
        """Every event in file order; an empty or absent log reads as no events."""
        if not self.path.exists():
            return []
        events: list[AuditEvent] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    events.append(AuditEvent.model_validate_json(line))
        return events

    def verify_chain(self) -> bool:
        """True if the whole file is one unbroken, unaltered chain; False otherwise.

        Unreadable or unparseable lines count as tampering, not as an error.
        """
        try:
            entries = self.read_all()
        except (ValidationError, json.JSONDecodeError):
            return False
        if not entries:
            return True
        if entries[0].prev_hash != GENESIS_HASH:
            return False
        for entry in entries:
            if hashlib.sha256(_canonical_bytes(entry)).hexdigest() != entry.entry_hash:
                return False
        for previous, entry in zip(entries, entries[1:], strict=False):
            if entry.prev_hash != previous.entry_hash:
                return False
        return True

    def _last_entry_hash(self) -> str:
        """entry_hash of the last line on disk, or GENESIS_HASH for a fresh/empty log.

        Raises on a corrupt last line: never chain onto an entry we cannot read.
        """
        last = ""
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        last = line.strip()
        if not last:
            return GENESIS_HASH
        return json.loads(last)["entry_hash"]
