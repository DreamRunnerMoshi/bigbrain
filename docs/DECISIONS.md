# Decisions (ADRs)

Context -> decision -> consequences, one entry per decision. Add entries whenever the spec
is ambiguous or the stack changes (CLAUDE.md working rules 3 and the spec section 3 rule).

## ADR-001 - Category taxonomy standard

**Context.** The prototype needs a canonical product category system to key pub/sub
channels. Two candidates: Google Product Taxonomy and Shopify's Standard Product Taxonomy.

**Decision.** Use Shopify Standard Product Taxonomy (open source, `shopify/product-taxonomy`
on GitHub) as the canonical channel-ID source, since merchants are Shopify stores. Keep
Google Product Taxonomy as a secondary cross-mapping for future non-Shopify merchants,
using Shopify's published mapping where available.

**Consequences.** Directory and profiler code key everything off Shopify taxonomy IDs;
Google IDs are optional/best-effort on intents and never required.

## ADR-002 - Tooling scaffold: uv + hatchling src layout, ruff, pytest

**Context.** M0 needs a runnable empty test suite and a passing lint, reproducible from a
lock file, on Python 3.12 (spec section 3). Python 3.12 is not the interpreter installed on
the machine (3.13 is), so the version must be pinned by the tooling, not by the shell.

**Decision.**

- `pyproject.toml` is a uv-managed, *packaged* project: `[build-system]` uses
  `hatchling.build` with `packages = ["src/bigbrain"]`, `requires-python = ">=3.12"`.
  `uv sync` therefore installs the package editable into `.venv`, so `import bigbrain`
  works in tests and a future `bigbrain` Typer CLI can be exposed as a console script
  without further config.
- `uv.lock` is committed; `.venv/` is not (see `.gitignore`).
- Test tooling lives in the `[dependency-groups].dev` group (pytest, pytest-asyncio,
  hypothesis, ruff). Runtime dependencies from spec section 3 (pydantic, fastapi, httpx,
  pynacl, typer, pandas, matplotlib, anthropic, etc.) are declared up front in
  `[project.dependencies]` so any milestone can start using them without a tooling PR.
- pytest is configured with `testpaths = ["tests"]`, `pythonpath = ["src"]`, and
  `addopts = "-ra -m 'not live'"`, with the `live` marker declared. Live Shopify tests are
  therefore skipped by default and opt-in via `uv run pytest -m live` (CLAUDE.md: live mode
  is opt-in; everything else must run offline).
- ruff: `line-length = 100`, `target-version = "py312"`, `src = ["src", "tests"]`,
  lint rules `E, W, F, I, B, UP, C4, SIM`, isort `known-first-party = ["bigbrain"]`.
  Formatting is the Ruff formatter (`make format`), checked with `make format-check`.
- Every `src/bigbrain/<module>/` and `tests/<kind>/` directory is a package with a
  one-line docstring `__init__.py` naming that subpackage's responsibility (verbatim from
  spec section 10's repo-layout comments), so test module names are unambiguous
  (`tests.unit.test_placeholder`) and subpackages are self-describing on import.

**Consequences.**

- `uv run pytest -q` and `uv run ruff check .` are the gates (also `make check`); CI and
  the milestone definition of done can rely on them.
- The `live` marker must be applied to every test that touches the network, or it will run
  in CI and fail without credentials.
- Adding a runtime dependency beyond spec section 3's list is a normal edit to
  `[project.dependencies]` plus `uv lock`/`uv sync`; changing the *stack* needs a new ADR.
- Python 3.12 is fetched by uv on first `uv sync` if it is not installed locally; the
  lock file keeps the resolution reproducible either way.

## ADR-003 - Audit log is hash-chained now, Ed25519-signed later

**Context.** BIGBRAIN_SPEC.md §7 and open problem #7 call for a signed, append-only audit
log, but signing keys don't exist until the M1 crypto module (`common/crypto.py`).

**Decision.** Implement a hash-chained JSONL append-only audit log in M0 as tamper-evident
storage (each entry stores `prev_hash` and its own `entry_hash = sha256(canonical_json)`).
Add real Ed25519 signatures over each entry once `common/crypto.py` exists in M1, without
changing the file format — hash chaining stays, a signature field gets added.

**Consequences.** M0's audit log proves an entry wasn't silently altered after the fact
once you have the whole file, but a compromised process could still fabricate a consistent
chain from scratch. That gap closes in M1.

## ADR-004 - Crypto primitives: which PyNaCl construction per message type

**Context.** BIGBRAIN_SPEC.md §6.5 assigns a construction per message type (SecretBox for
intents with a wrapped fresh key, SealedBox for offers, Box for counters/checkout, Ed25519
for envelope signatures) but leaves the concrete function shapes and key encoding open.

**Decision.**
- All keys are raw 32-byte values (not PyNaCl object types) at module boundaries, so they
  serialize as base64 on the wire and pass through pydantic string/bytes fields without a
  custom type. `common/crypto.py` wraps `nacl.signing`/`nacl.public`/`nacl.secret` and
  converts to/from raw bytes at the edges.
- `verify()` never raises — a bad signature, wrong-length key, or tampered data all return
  `False`, so call sites can implement I7 ("bad signatures are dropped and logged") without
  a try/except at every call site. `sign()`, and every `*_decrypt` function, DO raise
  (`nacl.exceptions.CryptoError` on a decrypt/MAC failure) — decryption failure is a
  different, rarer situation than "a message came in with a bad signature" and callers
  should see it explicitly rather than have it silently swallowed.
- `secretbox_encrypt`/`box_encrypt` return `(nonce, ciphertext)` as two separate values,
  matching the envelope's `nonce` / `ciphertext` wire fields directly (spec §6.1). PyNaCl's
  own `EncryptedMessage` already carries both; this module just splits them at the API
  boundary so callers never have to slice envelope-format bytes apart by hand.
- `sealedbox_encrypt` returns one self-contained blob (libsodium embeds a fresh ephemeral
  public key inside it, no separate nonce needed). For a PROPOSE (offer) envelope, the wire
  `nonce` field is therefore left as an empty string — SealedBox-sealed payloads don't have
  one. This is the simplest option that doesn't force a meaningless nonce into the schema
  for one message type.
- Key wrapping for intents (spec §6.2: "fresh symmetric key wrapped with the channel key")
  is not a separate function — it's just `secretbox_encrypt(channel_key, fresh_key)` using
  the same primitive twice (once to wrap the fresh key, once — with the fresh key — to
  encrypt the payload). No new primitive needed; the caller (the future `protocol`/`buyer`
  code that builds a CFP) composes the two calls.

**Consequences.** Everything downstream (envelope construction, the buyer/merchant
modules) works with raw bytes keys and gets a uniform `(nonce, ciphertext)` shape for the
two nonce-based schemes. Ed25519 signatures for the audit log (promised in ADR-003) are
still deferred past this module — wiring a worker's signing key into `AuditLog.record()`
needs worker identity/key management, which lands with the directory/worker milestones,
not here.

## ADR-005 - `MessageType` lives in `common/envelope.py`, `protocol/` re-exports it

**Context.** Spec §10's repo layout lists "performatives" as part of `protocol/`, but the
envelope's `type` field and its allowed values are defined by §6.1 (the envelope schema
itself), not by §6.2 (payloads). `common/` must not depend on `protocol/` — `protocol/`
is the higher layer that builds on `common/`'s primitives (crypto, canonical JSON, ids).

**Decision.** Define `MessageType` as part of `common/envelope.py`, since the `Envelope`
model's `type: MessageType` field needs it and `Envelope` itself lives in `common/` (per
§10's own module comment: "common: envelope, canonical json, crypto, ids, clock, config,
logging, audit"). `protocol/performatives.py` does `from bigbrain.common.envelope import
MessageType` and re-exports it, so protocol-layer code (state machine, payload builders)
imports it from the semantically-named location the spec's layout promises, without
inverting the dependency direction.

**Consequences.** One source of truth for message types, defined alongside the schema
that constrains them; `common/` stays free of any import from `protocol/`.
