"""Tests for bigbrain.common.envelope module.

Covers all 9 requirements:
1. Round-trip, sign/verify true
2. I7 - tamper tests on every message type (11 parametrized cases)
3. Tamper each field individually
4. Tampered signature
5. Wrong verify_key
6. JSON round-trip preserves verifiability
7. Empty nonce round-trips
8. Field validation
9. envelope_signing_bytes excludes sig
"""

import base64

import pytest
from pydantic import ValidationError

from bigbrain.common import (
    Envelope,
    MessageType,
    clock,
    crypto,
    envelope_signing_bytes,
    ids,
    sign_envelope,
    verify_envelope,
)


def make_envelope(msg_type: MessageType = MessageType.CFP) -> Envelope:
    """Factory: build a valid, unsigned Envelope with sensible dummy values.

    Raw bytes must be base64-encoded before passing to the Envelope constructor
    (per pydantic's Base64Bytes behavior -- it validates/decodes on construction).
    """
    raw_ciphertext = b"some ciphertext bytes"
    return Envelope(
        msg_id=ids.new_msg_id(),
        type=msg_type,
        session_id=ids.new_session_id(),
        intent_id=ids.new_msg_id(),
        round=0,
        sender="seller@example.com",
        recipient="buyer@example.com",
        key_epoch=0,
        sent_at=clock.rfc3339(clock.SystemClock().now()),
        ttl_s=3600,
        nonce=b"",
        ciphertext=base64.b64encode(raw_ciphertext),
    )


class TestRoundTrip:
    """Requirement 1: Round-trip, sign/verify true."""

    def test_sign_and_verify_round_trip(self):
        """Build envelope, sign, verify returns True."""
        envelope = make_envelope()
        signing_key, verify_key = crypto.generate_signing_keypair()

        signed_envelope = sign_envelope(envelope, signing_key)
        assert verify_envelope(signed_envelope, verify_key) is True


class TestTamperEveryMessageType:
    """Requirement 2: I7 - tamper tests on every message type (11 parametrized cases)."""

    @pytest.mark.parametrize("msg_type", list(MessageType))
    def test_tamper_ciphertext_all_message_types(self, msg_type: MessageType):
        """For each MessageType, build + sign envelope, corrupt ciphertext,
        verify returns False."""
        envelope = make_envelope(msg_type=msg_type)
        signing_key, verify_key = crypto.generate_signing_keypair()

        # Sign the envelope
        signed_envelope = sign_envelope(envelope, signing_key)
        assert verify_envelope(signed_envelope, verify_key) is True

        # Corrupt the ciphertext by prepending a byte (model_copy uses raw bytes)
        corrupted = signed_envelope.model_copy(
            update={"ciphertext": b"\xff" + signed_envelope.ciphertext}
        )

        # Verification should fail
        assert verify_envelope(corrupted, verify_key) is False


class TestTamperIndividualFields:
    """Requirement 3: Tamper each field individually."""

    def test_tamper_individual_fields(self):
        """For a single signed envelope, test tampering each field fails verification."""
        envelope = make_envelope()
        signing_key, verify_key = crypto.generate_signing_keypair()
        signed = sign_envelope(envelope, signing_key)

        # List of (field_name, new_value) pairs
        tampers = [
            ("msg_id", "tampered-id"),
            ("type", MessageType.PROPOSE),
            ("session_id", "tampered-session"),
            ("intent_id", "tampered-intent"),
            ("round", 1),
            ("sender", "attacker@example.com"),
            ("recipient", "victim@example.com"),
            ("key_epoch", 1),
            ("sent_at", "2099-01-01T00:00:00Z"),
            ("ttl_s", 7200),
            ("nonce", b"\xff" + signed.nonce),  # Append a byte to nonce
            ("ciphertext", b"\xff" + signed.ciphertext),  # Append a byte to ciphertext
        ]

        for field_name, new_value in tampers:
            tampered = signed.model_copy(update={field_name: new_value})
            assert verify_envelope(tampered, verify_key) is False, (
                f"Tampering {field_name} should fail verification"
            )


class TestTamperedSignature:
    """Requirement 4: Tampered signature."""

    def test_tamper_signature_fails_verification(self):
        """Flip a byte in sig, verify returns False."""
        envelope = make_envelope()
        signing_key, verify_key = crypto.generate_signing_keypair()
        signed = sign_envelope(envelope, signing_key)

        # Flip a byte in the signature
        tampered_sig = bytearray(signed.sig)
        tampered_sig[0] ^= 0xFF

        tampered = signed.model_copy(update={"sig": bytes(tampered_sig)})
        assert verify_envelope(tampered, verify_key) is False


class TestWrongVerifyKey:
    """Requirement 5: Wrong verify_key."""

    def test_wrong_verify_key_fails(self):
        """Sign with one keypair, verify with different keypair's verify_key."""
        envelope = make_envelope()
        signing_key1, verify_key1 = crypto.generate_signing_keypair()
        signing_key2, verify_key2 = crypto.generate_signing_keypair()

        signed = sign_envelope(envelope, signing_key1)
        # Verify with the wrong key
        assert verify_envelope(signed, verify_key2) is False


class TestJsonRoundTrip:
    """Requirement 6: JSON round-trip preserves verifiability."""

    def test_json_round_trip_preserves_verifiability(self):
        """Sign envelope, serialize/deserialize, verify still works."""
        envelope = make_envelope()
        signing_key, verify_key = crypto.generate_signing_keypair()

        signed = sign_envelope(envelope, signing_key)

        # JSON round-trip
        json_str = signed.model_dump_json()
        deserialized = Envelope.model_validate_json(json_str)

        # Verify the deserialized copy
        assert verify_envelope(deserialized, verify_key) is True

        # Envelopes should be equal
        assert deserialized == signed


class TestEmptyNonce:
    """Requirement 7: Empty nonce round-trips."""

    def test_empty_nonce_round_trips(self):
        """Build envelope with default nonce=b"", signs/verifies, survives JSON round-trip."""
        envelope = make_envelope()
        # Envelope factory uses nonce=b"" by default
        assert envelope.nonce == b""

        signing_key, verify_key = crypto.generate_signing_keypair()
        signed = sign_envelope(envelope, signing_key)

        # Should verify
        assert verify_envelope(signed, verify_key) is True

        # JSON round-trip
        json_str = signed.model_dump_json()
        deserialized = Envelope.model_validate_json(json_str)

        # nonce should be exactly b"", not None or missing
        assert deserialized.nonce == b""
        assert verify_envelope(deserialized, verify_key) is True


class TestFieldValidation:
    """Requirement 8: Field validation."""

    def test_negative_round_raises_validation_error(self):
        """Constructing with round=-1 raises ValidationError."""
        with pytest.raises(ValidationError):
            Envelope(
                msg_id=ids.new_msg_id(),
                type=MessageType.CFP,
                session_id=ids.new_session_id(),
                intent_id=ids.new_msg_id(),
                round=-1,
                sender="seller@example.com",
                recipient="buyer@example.com",
                key_epoch=0,
                sent_at=clock.rfc3339(clock.SystemClock().now()),
                ttl_s=3600,
                ciphertext=base64.b64encode(b"ciphertext"),
            )

    def test_zero_ttl_s_raises_validation_error(self):
        """Constructing with ttl_s=0 raises ValidationError."""
        with pytest.raises(ValidationError):
            Envelope(
                msg_id=ids.new_msg_id(),
                type=MessageType.CFP,
                session_id=ids.new_session_id(),
                intent_id=ids.new_msg_id(),
                round=0,
                sender="seller@example.com",
                recipient="buyer@example.com",
                key_epoch=0,
                sent_at=clock.rfc3339(clock.SystemClock().now()),
                ttl_s=0,
                ciphertext=base64.b64encode(b"ciphertext"),
            )

    def test_v_equals_2_raises_validation_error(self):
        """Constructing with v=2 raises ValidationError (Literal[1] constraint)."""
        with pytest.raises(ValidationError):
            Envelope(
                v=2,
                msg_id=ids.new_msg_id(),
                type=MessageType.CFP,
                session_id=ids.new_session_id(),
                intent_id=ids.new_msg_id(),
                round=0,
                sender="seller@example.com",
                recipient="buyer@example.com",
                key_epoch=0,
                sent_at=clock.rfc3339(clock.SystemClock().now()),
                ttl_s=3600,
                ciphertext=base64.b64encode(b"ciphertext"),
            )


class TestEnvelopeSigningBytesExcludesSig:
    """Requirement 9: envelope_signing_bytes excludes sig."""

    def test_signing_bytes_excludes_sig(self):
        """Two envelopes identical except sig produce same envelope_signing_bytes."""
        envelope1 = make_envelope()

        # Create a second with a different sig (via model_copy, which bypasses validation)
        envelope2 = envelope1.model_copy(update={"sig": b"different"})

        # Both should produce identical signing bytes
        bytes1 = envelope_signing_bytes(envelope1)
        bytes2 = envelope_signing_bytes(envelope2)

        assert bytes1 == bytes2
