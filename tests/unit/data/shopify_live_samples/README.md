# Live Shopify samples

Real, unmodified responses captured 2026-09-22 from `allbirds.com`'s public UCP/Storefront
MCP endpoints (public product catalog and store-policy data — nothing sensitive). Used as
ground-truth fixtures for `shopify/models.py` parsing tests, so those tests are checked
against real Shopify response shapes rather than synthetic data. See
`docs/SHOPIFY_NOTES.md` for what was confirmed from these captures.

Re-capture with `bigbrain shopify record` once that command exists, rather than hand-editing
these files.
