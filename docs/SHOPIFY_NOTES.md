# Shopify notes

What we confirmed against the live Shopify docs, and how Shopify actually behaved. Nothing
on this page is confirmed yet: it is the checklist M2 will work through. Per CLAUDE.md
working rule 1, verify against the live docs before writing any Shopify integration code,
and do not trust the summaries in CLAUDE.md, the spec, or this file.

Rule for every entry: date it, name the source URL, and quote the observed request/response
shape. Adjust code to what the docs and real responses say.

## Sources to check first (spec section 4)

- Storefront MCP server: https://shopify.dev/docs/apps/build/storefront-mcp/servers/storefront
- Storefront Catalog MCP (UCP tools): https://shopify.dev/docs/agents/catalog/storefront-catalog
- Shopify Catalog overview: https://shopify.dev/docs/agents/catalog
- UCP catalog specification (linked from the pages above)
- Shopify Standard Product Taxonomy: https://shopify.github.io/product-taxonomy/
- Shopify API License and Terms of Use (using these servers means agreeing to them)

## Endpoints

Status: **not verified.** To confirm, per endpoint: URL path, JSON-RPC version, auth
(expected: none), required headers, and `tools/list` output.

- [ ] Catalog (UCP): `POST https://{shop}/api/ucp/mcp` - tools `search_catalog`,
      `lookup_catalog`, `get_product`. Spec expects prices in minor units.
- [ ] Storefront (cart, policies): `POST https://{shop}/api/mcp` - tools
      `search_shop_policies_and_faqs`, `get_cart`, `update_cart`.
- [ ] Confirm `search_shop_catalog` is really deprecated and absent from `tools/list`.

## Agent profile (UCP request metadata)

Status: **not verified.** Expected: every request carries `meta.ucp-agent.profile` and the
tools a store returns depend on the advertised capabilities.

- [ ] Exact metadata field names and shape.
- [ ] Which capability IDs exist and which ones we need.
- [ ] Our BigBrain profile fields once created (never ship Shopify's example profile as our
      identity).

## Catalog listing / sampling

Status: **not verified.** The profiler depends on this (spec section 5.2).

- [ ] Does an empty or wildcard query list the catalog, or is a seed query set required?
- [ ] Pagination shape, page size limits, cursor semantics.
- [ ] Which filters are allowed on `search_catalog` (needed for the I11 allow-list: price
      range, country, currency, category - nothing else may go out).
- [ ] Whether responses carry a taxonomy category field (`source=shopify` classification).

## Response schema

Status: **not verified.**

- [ ] Field names/types for products, variants, price, availability, shipping, returns,
      warranty, condition.
- [ ] Error and restriction responses: what a restricted store returns, and how it differs
      from an empty result.
- [ ] Anything in responses we must scrub before committing a fixture.

## Politeness and restrictions

Status: **not verified.**

- [ ] Published rate limits / 429 behavior, and whether stores return 403 for agents.
- [ ] What a descriptive agent profile should contain beyond the UCP metadata.
- [ ] Caching window that is reasonable per store.

## Fixtures recorded so far

Status: none. Target for M2: committed cassettes for at least 5 diverse stores under
`fixtures/shopify/<shop>/`, scrubbed to public catalog/policy data only.
