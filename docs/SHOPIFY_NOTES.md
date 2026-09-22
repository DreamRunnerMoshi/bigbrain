# Shopify integration notes (M2)

Everything below was confirmed live on 2026-09-22 against real stores (`allbirds.com`,
`hydeline.com`) plus the docs pages listed in BIGBRAIN_SPEC.md §4. Where live behavior
disagreed with the docs or with the spec's own §5.1.1 summary, live behavior wins (spec
§0 instruction 5) and the disagreement is called out explicitly below. Do not trust this
file blindly either — Shopify can and does change this surface; re-verify before relying
on anything here for a real launch.

## Endpoints (confirmed live, both work directly on the custom domain — `.myshopify.com`
is not required even though one docs page's example used it)

| Endpoint | Path | Auth |
|---|---|---|
| UCP (catalog **+ cart + checkout + order**) | `POST https://{shop}/api/ucp/mcp` | none, but `meta.ucp-agent.profile` is enforced server-side (see below) |
| Storefront (policies only) | `POST https://{shop}/api/mcp` | none |

Both are JSON-RPC 2.0 (`tools/list`, `tools/call`), `Content-Type: application/json`.

### Disagreement #1 — tool placement is not what the spec or the docs say

BIGBRAIN_SPEC.md §5.1.1 says cart tools live at the plain `/api/mcp` endpoint. The
`storefront-mcp/servers/storefront` docs page agrees with the spec on that split. **Live
behavior on both probed stores contradicts both**: `/api/mcp` exposes exactly one tool,
`search_shop_policies_and_faqs`. Every other tool — the 3 catalog tools **and** cart,
checkout, and order tools — lives at `/api/ucp/mcp`. Confirmed identical tool set on both
stores:

```
/api/ucp/mcp:  get_checkout, create_checkout, update_checkout, complete_checkout,
               cancel_checkout, get_cart, create_cart, update_cart, cancel_cart,
               get_order, search_catalog, lookup_catalog, get_product
/api/mcp:      search_shop_policies_and_faqs
```

`search_shop_catalog` (the tool the spec says is deprecated, §5.1.1) does not appear in
either tool list on either store — consistent with "deprecated," or at least fully
retired from these two stores. We build only against `search_catalog` per the spec, so
this doesn't change anything, but don't go looking for `search_shop_catalog` in the code.

**Consequence for `ShopifyMCPClient`:** one client class, two base URLs
(`{shop}/api/ucp/mcp` for catalog/cart/checkout/order, `{shop}/api/mcp` for policies), not
the split the spec's module doc implies. `search_policies()` hits the plain endpoint;
everything else hits the UCP endpoint.

### Disagreement #2 — `search_shop_policies_and_faqs` has no `structuredContent`

Catalog/cart tool responses carry a `result.structuredContent` object with parsed JSON
(see below) **in addition to** the MCP-standard `result.content[0].text` string.
`search_shop_policies_and_faqs` has **no `structuredContent` field at all** — only
`result.content[0].text`, a JSON-encoded string: an array of `{"question": ..., "answer":
...}` objects. The client must parse `content[0].text` for this one tool specifically,
not assume `structuredContent` is universal.

## Agent profile (`meta.ucp-agent.profile`) — genuinely enforced, not just documented

Confirmed by omitting it entirely:

```
POST https://allbirds.com/api/ucp/mcp  (catalog: {query: "shoes"}, no meta at all)
-> HTTP 422
{"jsonrpc":"2.0","id":1,"error":{"code":-32001,"message":"UCP discovery failed",
 "data":{"code":"invalid_profile_url",
         "content":"Unable to fetch agent profile: Missing profile uri",
         "continue_url":"https://weareallbirds.myshopify.com/"}}}
```

The error text ("Unable to fetch agent profile") indicates Shopify's server actually
**fetches** the profile URL server-side. This means:

- Our own agent profile (spec §5.1.2: "Do not ship Shopify's example profile as our
  identity") must be a **real, publicly reachable URL** for live mode to work at all —
  a placeholder or `localhost` URL will fail every live call with this same error.
  `Settings.shopify_agent_profile_url` (already in `common/config.py`) holds it; ships
  unset by default (offline-safe), must be set to a real hosted URL to run live.
  Hosting that URL is an operational task outside this milestone's code — the profile
  JSON content itself is created as part of M2, hosting it is a deploy-time concern.
- Every request to every tool (catalog, cart, checkout, order) requires
  `meta.ucp-agent.profile`. `search_shop_policies_and_faqs` (plain `/api/mcp`) was NOT
  tested for this requirement and its schema (§5.1.1 lists no `meta` requirement for it)
  — treat it as not required there unless a live 422 says otherwise.

## `search_catalog` — real response shape (confirmed, `allbirds.com`)

Request:
```json
{"jsonrpc":"2.0","method":"tools/call","id":1,"params":{"name":"search_catalog",
 "arguments":{"meta":{"ucp-agent":{"profile":"<our-profile-url>"}},
              "catalog":{"query":"wool runner shoes","pagination":{"limit":2}}}}}
```

`result.structuredContent` (not just `content[0].text` — both carry the same data,
**parse `structuredContent`, it's already-parsed JSON**):

```
{
  "ucp": {...capabilities/version envelope, not product data...},
  "products": [
    {
      "id": "gid://shopify/Product/...",
      "title": "...",
      "description": {"html": "..."},      # <-- NOT "plain" -- see Disagreement #3
      "url": "...", "handle": "...",
      "price_range": {"min": {"amount": 11000, "currency": "USD"}, "max": {...}},
      "list_price_range": {"min": {"amount": 0, ...}, "max": {...}},  # compare-at; 0 = none
      "variants": [
        {"id": "gid://shopify/ProductVariant/...", "sku": "...", "title": "5",
         "description": {"html": "..."}, "price": {"amount": 11000, "currency": "USD"},
         "availability": {"available": true},
         "options": [{"name": "Size", "label": "5"}],
         "media": [{"type": "image", "url": "..."}],
         "requires": {"shipping": true},
         "checkout_url": "https://{shop}.myshopify.com/cart/{variant_id}:1"}
      ],
      "options": [{"name": "Size", "values": [{"label": "5"}, ...]}],
      "media": [...],
      "categories": [{"value": "gid://shopify/TaxonomyCategory/aa-8", "taxonomy": "shopify"}],
      "tags": ["allbirds::carbon-score => 7.07", ...],   # store-internal, often junk -- untrusted text, don't parse
      "gift_card": false,
      "collections": [{"id": "...", "handle": "...", "title": "...", "description": {"html": "..."}}]
    }
  ],
  "pagination": {"has_next_page": true, "cursor": "<opaque base64>"},
  "messages": []
}
```

### Disagreement #3 — `description` key is `html`, not `plain`

The **global** catalog (`catalog.shopify.com/api/ucp/mcp`, a different service — see
"Global vs Storefront" below) returns `description: {"plain": "..."}`. The **storefront**
catalog on both probed stores returns `description: {"html": "..."}`. Both are real,
confirmed shapes on real endpoints — this is not a typo in one or the other. `ShopProduct`
/`ShopVariant`'s description field must tolerate either key (`html: str | None = None`,
`plain: str | None = None`, both optional) rather than assuming one. Either way this text
is untrusted (spec §8.5) and HTML must not be rendered/trusted as-is.

`get_product` (single product, real GID from the search above): same product shape,
wrapped as `structuredContent: {"ucp": {...}, "product": {...same fields as above, plus
"selected": [...]...}, "messages": []}` — singular `product`, not `products`.

`lookup_catalog` was **not** live-probed this session (ran out of scope) — its documented
shape (`ids: [gid, ...]`, response grouped by product with `not_found` for unresolved
ids) should be spot-checked with `bigbrain shopify probe` before relying on it; the
`tools/list` schema for it is already captured in the fixture recordings.

## Filters — storefront `search_catalog` has a NARROWER filter set than the global catalog

The storefront `filters` object only has `categories`, `price` (min/max), `available` —
confirmed from the live `tools/list` schema. The **global** catalog's `filters` (seen
earlier against `catalog.shopify.com`) additionally has `shops`, `condition`, `ships_to`,
`ships_from`, `attributes`, `rating`, `price_tier`. Do not build `ShopDataSource.search`
code that assumes the full global filter set works against a single store — only pass
`categories`/`price`/`available` to a storefront `search_catalog` call.

`lookup_catalog` on the storefront accepts **up to 10 ids** per call (global: 50) —
confirmed from the live schema, matches the `catalog/storefront-catalog` docs page.

## Global vs Storefront Catalog — two different services

`catalog.shopify.com/api/ucp/mcp` (no `{shop}` — this is Shopify's own aggregator across
merchants) and `https://{shop}/api/ucp/mcp` (per-store) are **different backends** with
overlapping but not identical tool schemas (see Disagreement #3, and the filter-set
difference above). BIGBRAIN_SPEC.md's architecture (§5, §5.1.1) is built entirely on the
**per-store** endpoint — every BigBrainShop worker talks to exactly one store's own
`{shop}/api/ucp/mcp`. The global catalog is out of scope for M2 (spec §12 open problem #9
notes it as a future store-discovery mechanism, not part of the prototype's live path).

## Rate limits — no published numbers, tiered by identification

From `shopify.dev/docs/agents/profiles/auth-and-rate-limiting` (not independently
re-verified this session, only read): three tiers (Token/Signed/Anonymous) by
identification strength; anonymous gets the lowest limits and keyless access "doesn't
support increases" (confirmed wording, `catalog` overview page). No specific numbers are
published for any tier. `catalog` overview page: "Catalog queries are subject to rate
limits."

**Design consequence (I12):** since no numbers are published, the rate limiter must be
conservative and empirically tunable, not hard-coded to a documented ceiling. Default to
something clearly safe (e.g. 1 request/second/store, configurable), back off
exponentially on 429/5xx, and open a circuit (stop calling, mark the store `restricted`)
after a small number of consecutive failures — per spec I12's own requirement, not
because we know the real limit.

## Terms of use

Confirmed on the `storefront-mcp/servers/storefront` docs page: "By using the Shopify
MCP servers, you agree to the Shopify API License and Terms of Use." Not independently
re-read in full this session (spec §12 open problem #3 already flags legal review as a
pre-launch requirement, not a coding task).

## Cart response shape — NOT empirically confirmed

`get_cart`/`create_cart`/`update_cart` **input** schemas were captured live (see
`update_cart`'s `cart.line_items[].{id, quantity, item.id}` shape above), but their
*response* shape was not probed — calling `create_cart`/`update_cart` for real would
create a live cart on someone else's production store as a side effect of research,
which isn't a reasonable thing to do outside an actual purchase flow. `ShopCart` is
therefore inferred from the input schema and general Shopify cart conventions, not
confirmed from a real response. Spot-check it with a real `create_cart` call (in a
throwaway/test context) before M5 relies on it for real checkout handoff.

## What M2's code must NOT assume (recap for implementers)

1. Cart/checkout/order tools are on `/api/ucp/mcp`, not `/api/mcp`.
2. `search_shop_policies_and_faqs` has no `structuredContent` — parse `content[0].text`.
3. `description` may carry `html` or `plain` — model must tolerate either, treat both as
   untrusted text (spec §8.5).
4. `meta.ucp-agent.profile` is required and server-fetched on every UCP-endpoint call;
   missing/unreachable it is a hard 422, not a soft warning.
5. Storefront `search_catalog` filters are a strict subset of the global catalog's —
   don't build against the bigger global filter set.
6. `lookup_catalog` caps at 10 ids per call on the storefront (vs 50 globally).
