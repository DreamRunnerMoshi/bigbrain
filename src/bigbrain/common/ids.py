"""ID generation: RFC 9562 UUIDv7 for msg_id/intent_id/offer_id/event_id (time-ordered,
so IDs sort chronologically), and opaque random session ids per BIGBRAIN_SPEC.md section 6.1
("session_id: opaque random 128-bit, base64url").
"""

import base64
import os
import time
import uuid


def uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7: 48-bit unix-ms timestamp, version 7, variant 10, 74 random bits.

    Byte layout (16 bytes / 128 bits total):
      bytes[0:6]  -- unix_ts_ms, 48 bits, big-endian
      byte[6]     -- high nibble = 0b0111 (version 7), low nibble = top 4 random bits
      byte[7]     -- next 8 random bits (rand_a is 12 bits total: 4 from byte[6] + these 8)
      byte[8]     -- top 2 bits = 0b10 (variant), low 6 bits = start of rand_b
      bytes[9:16] -- remaining 56 random bits (rand_b is 62 bits total: 6 from byte[8] + these 56)
    """
    unix_ms = time.time_ns() // 1_000_000
    rand = os.urandom(10)
    b = bytearray(16)
    b[0:6] = unix_ms.to_bytes(6, "big")
    b[6] = 0x70 | (rand[0] & 0x0F)
    b[7] = rand[1]
    b[8] = 0x80 | (rand[2] & 0x3F)
    b[9:16] = rand[3:10]
    return uuid.UUID(bytes=bytes(b))


def new_msg_id() -> str:
    """New uuidv7 as a string, for msg_id / intent_id / offer_id / event_id fields."""
    return str(uuid7())


def new_session_id() -> str:
    """Opaque random 128-bit session id, base64url-encoded with no padding."""
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode("ascii")
