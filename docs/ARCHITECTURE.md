# Architecture

Summary only. The authoritative description is spec sections 5 (architecture), 6 (data
model and protocol) and 7 (operator trust); CLAUDE.md holds the invariants I1-I12.

## Component diagram

```
 Human --approve / open checkout URL--> BigBrain (buyer agent)
                                          |  ^
                           encrypted CFP  |  | sealed offers / revisions / checkout URL
                                          v  | (direct or via Mailbox)
  Directory <--resolve----------------  Broker (dumb pub/sub)
     ^  | admission + channel keys          | fan-out
     |  v                                   v
  Shop Profiler --profile--> BigBrainShop worker x N  (one per Shopify store, isolated)
                                          |  private index + policy cache
                                          v
                             Shopify Storefront MCP  (https://{shop}/api/...)
```

## Responsibilities

| Component | Package | Notes |
| --- | --- | --- |
| BigBrain (buyer agent) | `bigbrain.buyer` | intent builder, broadcaster, offer collector, scorer, negotiator, shortlist, approval gate (I1), checkout handoff |
| BigBrainShop (merchant agent) | `bigbrain.merchant` | one isolated worker per store: matcher, offer builder with provenance (I9), policy cache, cart (I10) |
| Shop Profiler | `bigbrain.profiler` | catalog sampling + category assignment -> `ShopProfile`; only admitted channel IDs reach the directory |
| Taxonomy | `bigbrain.taxonomy` | Shopify Standard Product Taxonomy loader, search, ancestor/depth utils, Google cross-map |
| Directory | `bigbrain.directory` | thin: category -> channel resolution, admission, key distribution; no product/price/catalog data (I3) |
| Broker | `bigbrain.broker` | dumb pub/sub over channel topics; validates envelopes, never decrypts (I2) |
| Mailbox | `bigbrain.mailbox` | ciphertext + routing metadata only; deletes on ack/TTL (I8) |
| Transport | `bigbrain.transport` | `Transport` interface: in-memory (sim/replay), WebSocket (net) |
| Shopify layer | `bigbrain.shopify` | `ShopifyMCPClient`, UCP models, per-store rate limiter/cache/backoff (I12), `ShopDataSource` implementations (live/replay/synthetic), fake MCP server |
| Common | `bigbrain.common` | envelope, canonical JSON, crypto (PyNaCl), ids, clock, config, logging, audit |
| Protocol | `bigbrain.protocol` | payload models, FIPA-style performatives, state machine |
| LLM (optional) | `bigbrain.llm` | client, prompts, cache, cost, defenses D0-D3; must work with no API key |
| Payments | `bigbrain.payments` | AP2 mock for the synthetic market only; agents never pay |
| UI | `bigbrain.ui` | Typer CLI first; minimal FastAPI + HTMX approval page later |

Supporting, non-package directories: `data/` (pinned taxonomy subset, store panel
`shops.yaml`), `fixtures/shopify/<shop>/` (recorded MCP cassettes), `sim/` (synthetic market,
human, attacks), `experiments/` (configs, intents, analysis).

## Runtime modes

Same code, selected by config, behind the `Transport` and `ShopDataSource` interfaces
(spec section 3):

| Mode | Transport | Merchant data |
| --- | --- | --- |
| `sim` | in-memory | synthetic market |
| `replay` | in-memory | recorded Shopify cassettes (default for dev and CI) |
| `live` | in-memory | real Shopify Storefront MCP |
| `net` | WebSocket, separate processes | replay or live |

Everything except `live`-Shopify tests must run offline with no API keys.

## Operator trust note (spec section 7)

BigBrain Inc. runs every BigBrainShop in this prototype, so BigBrain Inc. infrastructure
can decrypt intents inside its own shop workers. The prototype should make this visible,
not hide it:

- The protocol still keeps the broker, directory, mailbox, and Shopify blind to buyer
  identity and preferences, and keeps workers isolated from each other (I2, I4, I5).
- Workers log no decrypted intent content by default.
- `audit/` (append-only, per session) records what each worker decrypted and what it sent
  outward.
- Mitigations for later: claimed merchants running their own worker, TEEs, minimizing what
  workers decrypt. Tracked in spec section 12 (open problems 2 and 4).

## Invariants

I1-I12 are listed in CLAUDE.md with the required test for each; each also gets a test file
under `tests/invariants/` as the milestones land. Any change that could touch an invariant
must find and run its test first.
