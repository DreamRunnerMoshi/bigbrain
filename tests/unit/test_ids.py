"""Tests for bigbrain.common.ids module."""

import base64
import time
import uuid

from bigbrain.common.ids import new_msg_id, new_session_id, uuid7


class TestUUID7:
    """Test uuid7 function."""

    def test_version_is_7(self) -> None:
        """uuid7() produces UUIDs with version == 7."""
        u = uuid7()
        assert u.version == 7

    def test_variant_bits_correct(self) -> None:
        """RFC 4122 variant bits are correct (0b10)."""
        u = uuid7()

        # Check via the 128-bit integer: top 2 bits at position 62
        variant_bits = (u.int >> 62) & 0b11
        assert variant_bits == 0b10

        # Also verify directly from byte 8: top 2 bits should be 0b10
        assert (u.bytes[8] >> 6) == 0b10

    def test_monotonic_ordering(self) -> None:
        """Generate 1000 uuid7 values; verify RFC 9562 time-ordering and no duplicates."""
        values = []
        for i in range(1000):
            values.append(uuid7())
            # Space out UUIDs to ensure timestamp changes and monotonic ordering
            if (i + 1) % 100 == 0:
                time.sleep(0.001)

        # No duplicates (hard requirement per RFC 9562)
        assert len(set(values)) == 1000

        # Verify time-ordering: extract 48-bit timestamp from first 6 bytes
        # UUIDs with later timestamps should appear later in the list
        timestamps = [v.int >> 80 for v in values]  # Top 48 bits = unix_ms timestamp
        assert timestamps == sorted(timestamps)

        # Verify by byte representation: bytes[0:6] are the timestamp
        byte_timestamps = [int.from_bytes(v.bytes[0:6], "big") for v in values]
        assert byte_timestamps == sorted(byte_timestamps)


class TestNewMsgId:
    """Test new_msg_id function."""

    def test_returns_string_that_parses_as_uuid(self) -> None:
        """new_msg_id() returns a string that parses back via uuid.UUID()."""
        msg_id = new_msg_id()

        # Should be a string
        assert isinstance(msg_id, str)

        # Should parse without error
        parsed = uuid.UUID(msg_id)
        assert isinstance(parsed, uuid.UUID)


class TestNewSessionId:
    """Test new_session_id function."""

    def test_no_padding_characters(self) -> None:
        """Session ID contains no = padding characters."""
        sid = new_session_id()
        assert "=" not in sid

    def test_valid_base64url_roundtrip(self) -> None:
        """Session ID is valid base64url and round-trips correctly."""
        sid = new_session_id()

        # Add padding back for decoding
        padded = sid + "=="
        decoded = base64.urlsafe_b64decode(padded)

        # Should decode to exactly 16 bytes
        assert len(decoded) == 16

    def test_different_session_ids_are_different(self) -> None:
        """Two calls to new_session_id() produce different values."""
        sid1 = new_session_id()
        sid2 = new_session_id()

        assert sid1 != sid2
