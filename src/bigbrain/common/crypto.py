"""Cryptographic primitives: Ed25519 signing, X25519 keypairs, and three encryption
schemes per BIGBRAIN_SPEC.md section 6.5:
  - SecretBox (symmetric): used for intents, with a fresh key per intent wrapped by
    the channel's group key (envelope key_epoch identifies which channel key).
  - SealedBox (anonymous public-key): used for offers, sealed to the buyer's
    per-session reply_pubkey -- only the buyer can open it, not even the sender can
    reread its own ciphertext.
  - Box (authenticated public-key): used for counters and checkout messages between
    one buyer session and one agent.
All keys are raw bytes (32 bytes) so they serialize trivially (base64 on the wire,
per the envelope schema) and pass cleanly through pydantic models. No custom crypto:
this module is a thin wrapper over PyNaCl (libsodium) -- see spec section 3, and
docs/DECISIONS.md ADR-004 for the design rationale.
"""

import nacl.exceptions
import nacl.public
import nacl.secret
import nacl.signing
import nacl.utils

# ---- Ed25519 signing (envelope authenticity, I7) ----


def generate_signing_keypair() -> tuple[bytes, bytes]:
    """Return (signing_key_bytes, verify_key_bytes) -- 32 bytes each."""
    sk = nacl.signing.SigningKey.generate()
    return bytes(sk), bytes(sk.verify_key)


def sign(signing_key: bytes, data: bytes) -> bytes:
    """Detached Ed25519 signature over `data` (64 bytes)."""
    sk = nacl.signing.SigningKey(signing_key)
    return sk.sign(data).signature


def verify(verify_key: bytes, data: bytes, signature: bytes) -> bool:
    """True iff `signature` is a valid Ed25519 signature over `data` by `verify_key`.

    Never raises -- any malformed input (bad key length, bad signature, tampered
    data) simply returns False so callers can drop-and-log per I7 without a
    try/except at every call site.
    """
    try:
        nacl.signing.VerifyKey(verify_key).verify(data, signature)
        return True
    except (nacl.exceptions.BadSignatureError, ValueError, TypeError):
        return False


# ---- X25519 keypairs (encryption identity) ----


def generate_encryption_keypair() -> tuple[bytes, bytes]:
    """Return (private_key_bytes, public_key_bytes) -- 32 bytes each."""
    sk = nacl.public.PrivateKey.generate()
    return bytes(sk), bytes(sk.public_key)


# ---- SecretBox (symmetric: intents, channel keys) ----


def generate_symmetric_key() -> bytes:
    """Fresh random 32-byte key, e.g. for one intent or one channel epoch."""
    return nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE)


def secretbox_encrypt(key: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """Encrypt with a fresh random nonce. Returns (nonce, ciphertext) separately,
    matching the envelope's `nonce` / `ciphertext` wire fields.
    """
    box = nacl.secret.SecretBox(key)
    nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
    ciphertext = box.encrypt(plaintext, nonce).ciphertext
    return nonce, ciphertext


def secretbox_decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """Raises nacl.exceptions.CryptoError on a wrong key, wrong nonce, or tampered
    ciphertext -- callers decide whether that's a dropped/logged message (I7) or a
    real error, this function does not swallow it.
    """
    box = nacl.secret.SecretBox(key)
    return box.decrypt(ciphertext, nonce)


# ---- SealedBox (anonymous public-key: offers sealed to reply_pubkey) ----


def sealedbox_encrypt(recipient_public_key: bytes, plaintext: bytes) -> bytes:
    """Anonymous seal: only `recipient_public_key`'s holder can open this, and the
    sender's own identity is not embedded (a fresh ephemeral keypair is used
    internally by libsodium). One self-contained blob, no separate nonce -- the
    envelope's `nonce` field is left empty for SealedBox-sealed payloads (see
    docs/DECISIONS.md ADR-004).
    """
    sealed = nacl.public.SealedBox(nacl.public.PublicKey(recipient_public_key))
    return sealed.encrypt(plaintext)


def sealedbox_decrypt(recipient_private_key: bytes, ciphertext: bytes) -> bytes:
    """Raises nacl.exceptions.CryptoError if `ciphertext` wasn't sealed to the
    matching public key or was tampered with.
    """
    sealed = nacl.public.SealedBox(nacl.public.PrivateKey(recipient_private_key))
    return sealed.decrypt(ciphertext)


# ---- Box (authenticated public-key: counters, checkout messages) ----


def box_encrypt(
    my_private_key: bytes, their_public_key: bytes, plaintext: bytes
) -> tuple[bytes, bytes]:
    """Encrypt for a specific recipient, authenticated as coming from
    `my_private_key`'s holder. Returns (nonce, ciphertext) like secretbox_encrypt.
    """
    box = nacl.public.Box(
        nacl.public.PrivateKey(my_private_key), nacl.public.PublicKey(their_public_key)
    )
    nonce = nacl.utils.random(nacl.public.Box.NONCE_SIZE)
    ciphertext = box.encrypt(plaintext, nonce).ciphertext
    return nonce, ciphertext


def box_decrypt(
    my_private_key: bytes, their_public_key: bytes, nonce: bytes, ciphertext: bytes
) -> bytes:
    """Raises nacl.exceptions.CryptoError on a wrong key pairing or tampered ciphertext."""
    box = nacl.public.Box(
        nacl.public.PrivateKey(my_private_key), nacl.public.PublicKey(their_public_key)
    )
    return box.decrypt(ciphertext, nonce)
