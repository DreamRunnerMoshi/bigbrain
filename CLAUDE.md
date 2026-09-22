# CLAUDE.md — BigBrain prototype

This file orients any Claude Code session (or human) picking up this repo cold. Full spec: `../BIGBRAIN_SPEC.md` (read it before any milestone work — this file is a summary, not a replacement).

## What this is

BigBrain is a prototype of AI-agent-mediated shopping over real Shopify stores.

- **BigBrain** (buyer agent) — turns a human's need into a structured, encrypted **intent**, broadcasts it to a **category channel**, collects **sealed private offers** from merchant agents, negotiates over multiple rounds on multiple attributes (price, variant, shipping, returns, warranty — not just price), and presents a shortlist. The human always makes the final call and pays.
- **BigBrainShop** (merchant agent) — one per Shopify store, run by BigBrain Inc. as a "shadow agent" (the store owner did nothing to opt in). It reads the store via Shopify's public, unauthenticated **Storefront MCP** / **UCP catalog** endpoints, joins the category channels its catalog covers (decided by the **Shop Profiler**), and replies to intents with offers built only from real, freshly-fetched store data. It cannot cut prices — for real stores, "negotiation" means offering a better-matching variant/product, not a discount.
- **Directory** — thin: category→channel resolution + channel admission. Never stores catalog/price/intent data.
- **Broker** — dumb pub/sub. Never decrypts, never inspects beyond the envelope.
- **Mailbox** — store-and-forward ciphertext for offline buyers. Deletes on ack/TTL.
- **Checkout** — after human approval, the winning shop agent re-verifies the variant (price/availability may have changed) and creates a real Shopify cart; the human pays on Shopify's own checkout. Agents never touch payment.

Full glossary: spec §1.

## Hard invariants (I1–I12) — never break these

Every one of these has a required automated test (spec §2 has the exact test for each). If a change could touch one, find and run its test before considering the change done.

| # | Invariant |
|---|---|
| I1 | Human-final: no cart/checkout/`ACCEPT_PROPOSAL`/mandate without a signed human approval of that exact offer version. |
| I2 | Broker never holds keys or parses past the envelope. |
| I3 | Directory stores no product/inventory/price/catalog data. |
| I4 | Sealed bids: one BigBrainShop worker never sees another's offers; workers share no offer-bearing state. |
| I5 | Counters to shop A never leak shop B's terms. |
| I6 | Only channel-admitted shops can decrypt that channel's intents. |
| I7 | Every envelope is signed; bad signatures are dropped + logged. |
| I8 | Mailbox holds ciphertext + routing metadata only; deletes on ack/TTL. |
| I9 | Every offer term traces to real Shopify data with provenance, fetched within the freshness window; shadow agents never invent discounts or claim to be the merchant. |
| I10 | Re-verify the variant at approval time; changed terms require re-approval before checkout. |
| I11 | Outbound Shopify queries contain only derived keywords + allowed filters — never buyer identity, raw free text, weights, or reservation values. |
| I12 | Polite client: per-store rate limits, caching, backoff, descriptive agent profile, immediate stop on 403/429. |

## Tech stack (spec §3 — change only with an ADR in `docs/DECISIONS.md`)

Python 3.12 (`uv`-managed) · pydantic v2 strict · FastAPI/uvicorn + WebSockets · Shopify MCP via `mcp` SDK or thin JSON-RPC/`httpx` client · `respx`/`vcrpy` cassettes for Shopify fixtures · PyNaCl (libsodium) · SQLite everywhere · SQLite FTS5 for shop-worker search · pytest/pytest-asyncio/hypothesis (`@pytest.mark.live` skipped by default) · Anthropic SDK for optional LLM mode · Typer CLI · pandas/matplotlib for experiment reports.

Four runtime modes share the same code via `Transport` / `ShopDataSource` interfaces: `sim` (synthetic market), `replay` (recorded Shopify cassettes — default for dev/CI), `live` (real Shopify MCP), `net` (WebSocket, separate processes). **Everything except live-Shopify tests must run offline, no API keys.**

## Working rules

1. Before touching Shopify integration code, verify against the live docs (spec §4/§5.1.1), not against this file or the spec's guess at tool shapes — Shopify changes them. Record what you confirmed in `docs/SHOPIFY_NOTES.md`.
2. All randomness is seeded; every run must be reproducible from its config (or cassette, for live-Shopify).
3. When the spec is ambiguous, pick the simplest option that preserves the invariants and record it as an ADR in `docs/DECISIONS.md` (context → decision → consequences).
4. End each milestone with passing tests and an entry in `docs/PROGRESS.md`.
5. Full repo layout, protocol wire format, module responsibilities, experiments, and milestones: see spec §5–§11. Do not duplicate that detail here — read the spec section for the milestone you're on.

## Current status

See `docs/PROGRESS.md` for the latest milestone state.
