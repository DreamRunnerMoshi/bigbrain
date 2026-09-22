# Progress

One entry per milestone, newest first (CLAUDE.md working rule 4). Milestones and their
acceptance criteria are spec section 11.

## M2 - Shopify client & fixtures (done)

Done:

- `docs/SHOPIFY_NOTES.md`: written from LIVE verification (spec §0.5), not from the
  spec's or Shopify's docs' summaries. Confirmed real behavior disagrees with both in
  several places -- cart/checkout/order tools live at `/api/ucp/mcp` not `/api/mcp`;
  `search_shop_policies_and_faqs` has no `structuredContent`; product `description`
  uses `html` not `plain` on the storefront catalog (vs `plain` on the global
  catalog); the agent profile is genuinely server-fetched (missing/unreachable/wrong
  Content-Type all hard-fail with a 422); storefront vs global catalog use different
  product ID namespaces; an empty `query` lists the catalog (useful for M3's profiler).
- `shopify/models.py`: lenient pydantic models (`extra="ignore"`) for real Shopify
  data -- `Money`, `Description` (html/plain), `ShopProduct`, `ShopVariant`,
  `ShopPolicyAnswer`, `ShopCart`. Tested against real captured responses in
  `tests/unit/data/shopify_live_samples/`.
- `shopify/{ratelimit,cache,circuit}.py`: I12's "polite client" pieces -- async
  `TokenBucket`, injectable-clock `TTLCache`, `CircuitBreaker` with force-open for a
  hard 403 and threshold+cooldown decay for 429/5xx.
- `shopify/client.py`: `ShopifyMCPClient` -- one client per store, rate-limited,
  cached, circuit-broken, retrying with backoff, logging every call, with a
  descriptive `User-Agent`. Optional `record_path` writes a JSONL cassette.
- `shopify/datasource.py`: `ShopDataSource` protocol, `LiveShopify`, `ReplayShopify`
  (reads the cassette `ShopifyMCPClient` writes, exact-match lookup, raises
  `FixtureNotFoundError` rather than guessing).
- `shopify/fake_server.py`: `FakeShopifyMCPServer` (FastAPI), serves cassettes over
  the same JSON-RPC shape for offline net-mode/CI, proven protocol-compatible with a
  real `ShopifyMCPClient` via `httpx.ASGITransport`.
- `ui/cli.py`: `bigbrain shopify probe`/`record`, wired as the `bigbrain` console
  script.
- `data/agent_profile.json`: our own UCP agent profile (not Shopify's example),
  hosted live via jsDelivr against this repo's own GitHub mirror (GitHub Gist raw
  URLs don't work -- wrong Content-Type; see SHOPIFY_NOTES.md).
- **Real bug found and fixed via live recording**: `search_catalog`/`lookup_catalog`/
  `get_product` read `result["products"]`/`result["product"]` directly instead of
  `result["structuredContent"]["products"]`/`["product"]`. Every unit test passed
  because the mocks were built by extracting `structuredContent` and using it AS the
  mocked `result`, silently agreeing with the same bug. Caught only by running
  `bigbrain shopify record` against a real store. Fixed with a small `_unwrap()`
  helper in both `ShopifyMCPClient` and `ReplayShopify`; every affected test mock
  rewritten to the correct, fully-nested real shape. Full account in
  `docs/SHOPIFY_NOTES.md`.
- Fixtures recorded live for 5 diverse stores (spec's example verticals):
  `allbirds.com` (apparel), `hydeline.com` (home goods), `nomadgoods.com`
  (electronics accessories), `colourpop.com` (beauty), `magicspoon.com`
  (food/beverage). Each replays correctly through `ReplayShopify` and
  `FakeShopifyMCPServer`.
- I11 audit: explicit tests inspecting real outbound request bodies against an
  allow-list (necessary-but-not-sufficient -- the matcher layer, a later milestone,
  is what decides what's safe to send in the first place).

Verification: `uv run pytest -q` -> 232 passed, 0 deselected; `uv run ruff check .`
and `uv run ruff format --check .` -> clean; `bigbrain shopify probe` run live
against 5 real stores; `bigbrain shopify record` run live against the same 5,
producing the committed fixtures.

Next: M3 - Taxonomy & Shop Profiler (taxonomy loader/utilities, catalog sampling,
rule-based category assignment, aggregation, `ShopProfile`, `ShopifyAdmissionPolicy`,
directory admission).

## M1 - Wire format and crypto (done)

Done:

- `common/canonical.py`: `canonical_json_bytes()` -- the one shared canonical-JSON
  function (sorted keys, no whitespace, UTF-8) used by both `common/audit.py` (refactored
  to use it instead of its own private copy) and `common/envelope.py`.
- `common/ids.py`: `uuid7()` (RFC 9562 UUIDv7, hand-verified bit layout: version/variant
  nibbles, monotonic ordering), `new_msg_id()`, `new_session_id()` (opaque random 128-bit,
  base64url).
- `common/clock.py`: `SystemClock`/`FixedClock`/`Clock` protocol, `rfc3339()`.
- `common/crypto.py` (ADR-004): thin PyNaCl wrapper -- Ed25519 `sign`/`verify` (`verify`
  never raises, for I7 drop-and-log), `SecretBox` (intents), `SealedBox` (offers sealed to
  `reply_pubkey`), `Box` (counters/checkout). 18 property tests: round-trips, wrong-key and
  tampered-ciphertext failures, nonce/ephemeral-key freshness.
- `common/envelope.py`: the signed `Envelope` (spec section 6.1) -- `Base64Bytes` fields
  for `nonce`/`ciphertext`/`sig`, `sign_envelope`/`verify_envelope` over
  `envelope_signing_bytes` (canonical JSON, `sig` excluded). `MessageType` lives here, not
  in `protocol/` (ADR-005); `protocol/performatives.py` re-exports it. 21 tests: sign/verify
  round-trip, I7 tamper coverage across all 11 message types, per-field tamper, JSON
  round-trip, empty-nonce (SealedBox) case, field validation.
- `protocol/payloads.py`: the 14 inner payload models (spec section 6.2) -- Intent,
  Offer (+ Shop/Item/Terms/Provenance/ShopText), Counter, CheckoutRequest,
  CheckoutReady, Failure. ADR-006: CheckoutReady/Failure split 1:1 with envelope
  type=CHECKOUT_READY/FAILURE; offer revisions reuse `Offer` with a bumped
  `offer_version` rather than a separate class. 41 tests: round-trip + extra-field-rejected
  per model, every numeric/literal constraint.
- `protocol/state_machine.py`: `SessionState` (16 states), explicit `TRANSITIONS` table
  (ADR-007 pins down the edges spec section 6.4's diagram leaves implicit -- which states
  reach `EXPIRED`/`REJECTED_ALL`), `IllegalTransitionError`, `SessionStateMachine`. 36
  tests, including an exhaustive check over the full 16x16 state product (235 illegal
  pairs, all raise; 21 legal edges, all succeed) plus every named path from spec 6.4
  (Shopify checkout, sim/AP2 mandate, re-approval loop, rejected-all, expiry from every
  waiting state).
- ADR-004 through ADR-007 in `docs/DECISIONS.md` record every non-obvious design call
  this milestone made beyond the spec's literal text.

Verification: `uv run pytest -q` -> 148 passed, 0 deselected; `uv run ruff check .` and
`uv run ruff format --check .` -> clean.

Next: M2 - Shopify client & fixtures (read the live docs first, write
`docs/SHOPIFY_NOTES.md`, implement the MCP client, UCP models, rate limiter, cache, agent
profile, `probe`/`record` CLI commands, `ReplayShopify`, `FakeShopifyMCPServer`, record
fixtures for >=5 stores).

## M0 - Skeleton and tooling (done)

Done so far:

- Repo skeleton, directory layout, and `CLAUDE.md` were already in place before this entry.
- `pyproject.toml`: uv-managed Python 3.12 project, src layout, hatchling build backend,
  pytest config (`tests/`, `src` on `pythonpath`, `live` marker deselected by default) and
  ruff config (line length 100, target py312).
- Dev toolchain in the `dev` dependency group: pytest, pytest-asyncio, hypothesis, ruff.
  Runtime dependencies from spec section 3 (pydantic, fastapi, uvicorn, websockets, httpx,
  respx, vcrpy, pynacl, typer, pandas, matplotlib, anthropic) are declared in
  `[project.dependencies]` up front. `uv.lock` is committed.
- `Makefile` targets: `sync`, `test`, `lint`, `format`, `format-check`, `check`, `clean`,
  `help`. `make test` is the M0 entry point.
- `.gitignore` (venv, caches, build output, experiment `results/`, local env files).
- `README.md`: setup, test/lint commands, layout summary.
- `__init__.py` for every package under `src/bigbrain/` and every test directory.
- `tests/unit/test_placeholder.py`: the only test file, asserting the package and its
  subpackages import. Replace it once M1 code lands.
- `docs/`: `PROGRESS.md`, `DECISIONS.md` (ADR-001, ADR-002), `ARCHITECTURE.md`, `SHOPIFY_NOTES.md`
  (stub, nothing verified yet), `FINDINGS.md` (stub).
- `common/config.py`: strict pydantic v2 `Settings` with the `RuntimeMode` enum covering the
  four modes of spec section 3, plus `load_config()` over an optional YAML file (defaults when
  the path is None/missing/empty, pydantic `ValidationError` on bad values). Default mode is
  REPLAY -- offline, no API keys. `pyyaml` added to `[project.dependencies]` for this.
- `common/logging.py`: `setup_logging()` configures the `bigbrain` logger (never the root
  logger) with a single stderr handler and ISO-8601 UTC timestamps, idempotently;
  `get_logger(name)` returns `bigbrain.<name>`. Callers must never log decrypted intent/offer
  plaintext (spec section 7); the structured audit trail is below.
- `common/audit.py`: append-only, hash-chained JSONL audit log (`AuditLog`, `AuditEvent`,
  `GENESIS_HASH`), one `<session_id>.jsonl` per session, each entry chaining to the previous
  `entry_hash = sha256(canonical JSON)`; `verify_chain()` walks the file. Unsigned for now --
  Ed25519 signatures land in M1 per ADR-003.
- `common/__init__.py` re-exports the three modules' public names.
- `tests/unit/test_config.py`, `test_logging.py`, `test_audit.py`: config loading and
  validation, logging idempotency, chain building across re-opened logs, tamper detection.

Verification: `uv run pytest -q` -> 16 passed, 0 deselected; `uv run ruff check .` -> clean.
