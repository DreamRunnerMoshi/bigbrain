"""Performatives: FIPA Contract Net + BigBrain's checkout extension (spec sections 4, 6.1).
Re-exports MessageType from common/envelope.py -- the envelope schema is the single source
of truth for the wire `type` field's allowed values (docs/DECISIONS.md ADR-005).
"""

from bigbrain.common.envelope import MessageType

__all__ = ["MessageType"]
