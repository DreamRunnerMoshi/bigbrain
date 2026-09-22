"""The outer wire envelope, unchanged from v1 (BIGBRAIN_SPEC.md section 6.1). Every
message on the wire -- CFP, PROPOSE, COUNTER, CHECKOUT_REQUEST, etc. -- is one signed
Envelope; the broker and mailbox only ever see this shape (I2, I8). `ciphertext` holds
the encrypted inner payload (see protocol/payloads.py, added separately, for what's
inside once decrypted).
"""

from enum import Enum
from typing import Literal

from pydantic import Base64Bytes, BaseModel, ConfigDict, Field

from bigbrain.common.canonical import canonical_json_bytes
from bigbrain.common.crypto import sign, verify


class MessageType(str, Enum):
    """The performatives of BIGBRAIN_SPEC.md section 6.1's `type` field (FIPA Contract Net
    + BigBrain's checkout extension, spec section 4). Defined here (not in protocol/)
    because these are the envelope schema's own allowed values; protocol/performatives.py
    re-exports this rather than redefining it (docs/DECISIONS.md ADR-005).
    """

    CFP = "CFP"
    PROPOSE = "PROPOSE"
    REFUSE = "REFUSE"
    COUNTER = "COUNTER"
    REJECT_PROPOSAL = "REJECT_PROPOSAL"
    ACCEPT_PROPOSAL = "ACCEPT_PROPOSAL"
    INFORM_DONE = "INFORM_DONE"
    FAILURE = "FAILURE"
    WITHDRAW = "WITHDRAW"
    CHECKOUT_REQUEST = "CHECKOUT_REQUEST"
    CHECKOUT_READY = "CHECKOUT_READY"


class Envelope(BaseModel):
    """The signed outer envelope. `nonce` is empty for SealedBox-sealed payloads
    (ADR-004); `ciphertext` and `sig` are always present. Build one, call
    `sign_envelope()` to fill `sig`, then `verify_envelope()` on the receiving side.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    v: Literal[1] = 1
    msg_id: str
    type: MessageType
    session_id: str
    intent_id: str
    round: int = Field(ge=0)
    sender: str
    recipient: str
    key_epoch: int = Field(ge=0)
    sent_at: str
    ttl_s: int = Field(gt=0)
    nonce: Base64Bytes = b""
    ciphertext: Base64Bytes
    sig: Base64Bytes = b""


def envelope_signing_bytes(envelope: Envelope) -> bytes:
    """Canonical JSON of every field except `sig` -- the exact input `sig` covers
    (spec section 6.1: "sig: Ed25519 over canonical JSON of all fields above").
    """
    return canonical_json_bytes(envelope.model_dump(mode="json", exclude={"sig"}))


def sign_envelope(envelope: Envelope, signing_key: bytes) -> Envelope:
    """Return a copy of `envelope` with `sig` set. `envelope.sig` beforehand is
    irrelevant -- it is excluded from the signed bytes either way.
    """
    signature = sign(signing_key, envelope_signing_bytes(envelope))
    return envelope.model_copy(update={"sig": signature})


def verify_envelope(envelope: Envelope, verify_key: bytes) -> bool:
    """True iff `envelope.sig` is a valid signature over the envelope's other fields
    by `verify_key`. Never raises (I7: bad signatures are dropped and logged, not
    exceptions) -- delegates to crypto.verify(), which has the same guarantee.
    """
    return verify(verify_key, envelope_signing_bytes(envelope), envelope.sig)
