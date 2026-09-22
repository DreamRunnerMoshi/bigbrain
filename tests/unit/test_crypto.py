"""Tests for bigbrain.common.crypto module.

Covers all 18 required properties:
1-6: Signing (keypair generation, sign/verify, robustness to tampered data/keys)
7-11: SecretBox (symmetric encryption, randomness, error handling)
12-14: SealedBox (anonymous seal, randomness, error handling)
15-17: Box (authenticated public-key encryption, multi-party, randomness)
18: Encryption keypair generation
"""

import nacl.exceptions
import pytest

from bigbrain.common import crypto


class TestSigning:
    """Properties 1-6: Ed25519 signing and verification."""

    def test_sign_and_verify_with_matching_key(self):
        """Property 1: sign() then verify() with matching verify_key returns True."""
        signing_key, verify_key = crypto.generate_signing_keypair()
        data = b"test message"
        signature = crypto.sign(signing_key, data)
        assert crypto.verify(verify_key, data, signature) is True

    def test_verify_with_different_keypair_returns_false(self):
        """Property 2: verify() with different keypair's verify_key returns False."""
        signing_key1, verify_key1 = crypto.generate_signing_keypair()
        signing_key2, verify_key2 = crypto.generate_signing_keypair()
        data = b"test message"
        signature = crypto.sign(signing_key1, data)
        # Verify with the wrong keypair's verify_key
        assert crypto.verify(verify_key2, data, signature) is False

    def test_verify_with_tampered_data_returns_false(self):
        """Property 3: verify() against tampered data returns False."""
        signing_key, verify_key = crypto.generate_signing_keypair()
        data = b"test message"
        signature = crypto.sign(signing_key, data)
        # Tamper with the data
        tampered_data = b"tampered message"
        assert crypto.verify(verify_key, tampered_data, signature) is False

    def test_verify_with_tampered_signature_returns_false(self):
        """Property 4: verify() against tampered signature returns False."""
        signing_key, verify_key = crypto.generate_signing_keypair()
        data = b"test message"
        signature = crypto.sign(signing_key, data)
        # Tamper with the signature by flipping a byte
        tampered_signature = bytearray(signature)
        tampered_signature[0] ^= 0xFF
        assert crypto.verify(verify_key, data, bytes(tampered_signature)) is False

    def test_verify_with_malformed_key_returns_false(self):
        """Property 5: verify() with malformed verify_key returns False (no raise)."""
        signing_key, _ = crypto.generate_signing_keypair()
        data = b"test message"
        signature = crypto.sign(signing_key, data)
        # Use a malformed key (too short)
        malformed_key = b"too-short"
        # Should return False, not raise an exception
        assert crypto.verify(malformed_key, data, signature) is False

    def test_generate_signing_keypair_properties(self):
        """Property 6: generate_signing_keypair() returns 32-byte keys, two calls differ."""
        sk1, vk1 = crypto.generate_signing_keypair()
        sk2, vk2 = crypto.generate_signing_keypair()

        # Both keys should be 32 bytes
        assert len(sk1) == 32
        assert len(vk1) == 32
        assert len(sk2) == 32
        assert len(vk2) == 32

        # Two calls should produce different keypairs
        assert sk1 != sk2
        assert vk1 != vk2


class TestSecretBox:
    """Properties 7-11: Symmetric encryption (SecretBox)."""

    def test_secretbox_encrypt_decrypt_with_same_key(self):
        """Property 7: secretbox_encrypt then secretbox_decrypt returns original plaintext."""
        key = crypto.generate_symmetric_key()
        plaintext = b"secret intent message"
        nonce, ciphertext = crypto.secretbox_encrypt(key, plaintext)
        decrypted = crypto.secretbox_decrypt(key, nonce, ciphertext)
        assert decrypted == plaintext

    def test_secretbox_decrypt_with_wrong_key_raises(self):
        """Property 8: secretbox_decrypt with wrong key raises CryptoError."""
        key1 = crypto.generate_symmetric_key()
        key2 = crypto.generate_symmetric_key()
        plaintext = b"secret intent message"
        nonce, ciphertext = crypto.secretbox_encrypt(key1, plaintext)

        # Decrypt with wrong key should raise
        with pytest.raises(nacl.exceptions.CryptoError):
            crypto.secretbox_decrypt(key2, nonce, ciphertext)

    def test_secretbox_decrypt_with_tampered_ciphertext_raises(self):
        """Property 9: secretbox_decrypt with tampered ciphertext raises CryptoError."""
        key = crypto.generate_symmetric_key()
        plaintext = b"secret intent message"
        nonce, ciphertext = crypto.secretbox_encrypt(key, plaintext)

        # Tamper with the ciphertext
        tampered_ciphertext = bytearray(ciphertext)
        tampered_ciphertext[0] ^= 0xFF
        tampered_ciphertext = bytes(tampered_ciphertext)

        # Decrypt with tampered ciphertext should raise
        with pytest.raises(nacl.exceptions.CryptoError):
            crypto.secretbox_decrypt(key, nonce, tampered_ciphertext)

    def test_secretbox_encrypt_uses_fresh_nonce(self):
        """Property 10: Two calls to secretbox_encrypt produce different nonces and ciphertexts."""
        key = crypto.generate_symmetric_key()
        plaintext = b"secret intent message"

        nonce1, ciphertext1 = crypto.secretbox_encrypt(key, plaintext)
        nonce2, ciphertext2 = crypto.secretbox_encrypt(key, plaintext)

        # Nonces should be different (fresh random each time)
        assert nonce1 != nonce2
        # Ciphertexts should be different (because nonces differ)
        assert ciphertext1 != ciphertext2

    def test_generate_symmetric_key_properties(self):
        """Property 11: generate_symmetric_key() returns 32 bytes, two calls differ."""
        key1 = crypto.generate_symmetric_key()
        key2 = crypto.generate_symmetric_key()

        # Both should be 32 bytes
        assert len(key1) == 32
        assert len(key2) == 32

        # Two calls should produce different keys
        assert key1 != key2


class TestSealedBox:
    """Properties 12-14: Anonymous public-key encryption (SealedBox)."""

    def test_sealedbox_encrypt_decrypt_with_matching_key(self):
        """Property 12: sealedbox_encrypt then sealedbox_decrypt returns original plaintext."""
        priv_key, pub_key = crypto.generate_encryption_keypair()
        plaintext = b"sealed offer"
        ciphertext = crypto.sealedbox_encrypt(pub_key, plaintext)
        decrypted = crypto.sealedbox_decrypt(priv_key, ciphertext)
        assert decrypted == plaintext

    def test_sealedbox_decrypt_with_unrelated_key_raises(self):
        """Property 13: sealedbox_decrypt with unrelated private key raises CryptoError."""
        priv_key1, pub_key1 = crypto.generate_encryption_keypair()
        priv_key2, pub_key2 = crypto.generate_encryption_keypair()
        plaintext = b"sealed offer"
        ciphertext = crypto.sealedbox_encrypt(pub_key1, plaintext)

        # Decrypt with unrelated private key should raise
        with pytest.raises(nacl.exceptions.CryptoError):
            crypto.sealedbox_decrypt(priv_key2, ciphertext)

    def test_sealedbox_encrypt_uses_fresh_ephemeral_key(self):
        """Property 14: Two calls to sealedbox_encrypt produce different ciphertexts."""
        priv_key, pub_key = crypto.generate_encryption_keypair()
        plaintext = b"sealed offer"

        ciphertext1 = crypto.sealedbox_encrypt(pub_key, plaintext)
        ciphertext2 = crypto.sealedbox_encrypt(pub_key, plaintext)

        # Even with the same plaintext and recipient, ciphertexts should differ
        # (fresh ephemeral key each time)
        assert ciphertext1 != ciphertext2


class TestBox:
    """Properties 15-17: Authenticated public-key encryption (Box)."""

    def test_box_two_party_encryption(self):
        """Property 15: Alice encrypts to Bob, Bob decrypts and gets original message."""
        # Alice's keypair
        alice_priv, alice_pub = crypto.generate_encryption_keypair()
        # Bob's keypair
        bob_priv, bob_pub = crypto.generate_encryption_keypair()

        message = b"checkout message from alice to bob"

        # Alice encrypts to Bob
        nonce, ciphertext = crypto.box_encrypt(alice_priv, bob_pub, message)

        # Bob decrypts (using his private key and Alice's public key)
        decrypted = crypto.box_decrypt(bob_priv, alice_pub, nonce, ciphertext)

        assert decrypted == message

    def test_box_decrypt_with_unrelated_key_raises(self):
        """Property 16: Decrypting with unrelated third party's key raises CryptoError."""
        alice_priv, alice_pub = crypto.generate_encryption_keypair()
        bob_priv, bob_pub = crypto.generate_encryption_keypair()
        charlie_priv, charlie_pub = crypto.generate_encryption_keypair()

        message = b"checkout message from alice to bob"

        # Alice encrypts to Bob
        nonce, ciphertext = crypto.box_encrypt(alice_priv, bob_pub, message)

        # Charlie (unrelated third party) tries to decrypt with his private key
        # and Alice's public key (wrong pairing)
        with pytest.raises(nacl.exceptions.CryptoError):
            crypto.box_decrypt(charlie_priv, alice_pub, nonce, ciphertext)

    def test_box_encrypt_uses_fresh_nonce(self):
        """Property 17: Two calls to box_encrypt produce different nonces and ciphertexts."""
        alice_priv, alice_pub = crypto.generate_encryption_keypair()
        bob_priv, bob_pub = crypto.generate_encryption_keypair()
        message = b"checkout message"

        nonce1, ciphertext1 = crypto.box_encrypt(alice_priv, bob_pub, message)
        nonce2, ciphertext2 = crypto.box_encrypt(alice_priv, bob_pub, message)

        # Nonces should be different
        assert nonce1 != nonce2
        # Ciphertexts should be different (because nonces differ)
        assert ciphertext1 != ciphertext2


class TestEncryptionKeypair:
    """Property 18: Encryption keypair generation."""

    def test_generate_encryption_keypair_properties(self):
        """Property 18: generate_encryption_keypair() returns 32-byte keys, two calls differ."""
        priv1, pub1 = crypto.generate_encryption_keypair()
        priv2, pub2 = crypto.generate_encryption_keypair()

        # Both keys should be 32 bytes
        assert len(priv1) == 32
        assert len(pub1) == 32
        assert len(priv2) == 32
        assert len(pub2) == 32

        # Two calls should produce different keypairs
        assert priv1 != priv2
        assert pub1 != pub2
