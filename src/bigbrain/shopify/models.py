"""Pydantic models for real Shopify UCP/Storefront MCP responses (BIGBRAIN_SPEC.md
section 5.1.3). These parse EXTERNAL, Shopify-controlled data -- unlike
protocol/payloads.py's strict internal wire models, these are deliberately lenient:
unknown fields are kept in `raw` for debugging but never trusted for decisions (spec
section 5.1.3), and known fields use sensible defaults rather than raising when a real
store's response is missing something docs/SHOPIFY_NOTES.md didn't anticipate. All text
fields (titles, descriptions, policy answers) are UNTRUSTED input (spec section 8.5) --
never used for decisions past the point of structured field extraction. See
docs/SHOPIFY_NOTES.md for exactly what was confirmed live and where it disagrees with
the spec's own summary or Shopify's docs pages.
"""

from pydantic import BaseModel, ConfigDict, Field


class Money(BaseModel):
    """{"amount": 11000, "currency": "USD"} == $110.00 -- integer minor units
    (docs/SHOPIFY_NOTES.md, confirmed live)."""

    model_config = ConfigDict(extra="ignore")

    amount: int
    currency: str


class Description(BaseModel):
    """Either "html" or "plain" depending on which Shopify surface answered --
    docs/SHOPIFY_NOTES.md Disagreement #3: the storefront catalog uses "html", the
    global catalog uses "plain". Both optional, both untrusted text (spec section 8.5).
    """

    model_config = ConfigDict(extra="ignore")

    html: str | None = None
    plain: str | None = None


class MediaItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str | None = None
    url: str | None = None


class VariantOption(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    label: str | None = None


class Availability(BaseModel):
    model_config = ConfigDict(extra="ignore")

    available: bool | None = None


class PriceRange(BaseModel):
    model_config = ConfigDict(extra="ignore")

    min: Money | None = None
    max: Money | None = None


class TaxonomyCategory(BaseModel):
    """One taxonomy category attached to a product (spec section 5.1.3, section 5.2 --
    the Shop Profiler reads this field, added in a later milestone)."""

    model_config = ConfigDict(extra="ignore")

    value: str | None = None
    taxonomy: str | None = None


class ShopVariant(BaseModel):
    """One purchasable variant of a ShopProduct (spec section 5.1.3). Confirmed live
    shape in docs/SHOPIFY_NOTES.md's `search_catalog` section.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    sku: str | None = None
    title: str | None = None
    description: Description | None = None
    price: Money | None = None
    availability: Availability | None = None
    options: list[VariantOption] = Field(default_factory=list)
    media: list[MediaItem] = Field(default_factory=list)
    checkout_url: str | None = None
    raw: dict = Field(default_factory=dict)


class ShopProduct(BaseModel):
    """One product from search_catalog / get_product / lookup_catalog (spec section
    5.1.3). Confirmed live shape in docs/SHOPIFY_NOTES.md's `search_catalog` section.
    `tags` and `collections` are deliberately NOT modeled as structured fields -- they're
    store-internal and often junk (docs/SHOPIFY_NOTES.md: "often junk, untrusted text,
    don't parse") -- they land in `raw` along with everything else not listed here.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str | None = None
    description: Description | None = None
    url: str | None = None
    handle: str | None = None
    price_range: PriceRange | None = None
    variants: list[ShopVariant] = Field(default_factory=list)
    media: list[MediaItem] = Field(default_factory=list)
    categories: list[TaxonomyCategory] = Field(default_factory=list)
    gift_card: bool | None = None
    raw: dict = Field(default_factory=dict)


class ShopPolicyAnswer(BaseModel):
    """One {question, answer} pair from search_shop_policies_and_faqs (spec section
    5.1.3). IMPORTANT: this tool's response has NO `structuredContent` field
    (docs/SHOPIFY_NOTES.md, Disagreement #2) -- the caller (the client, added in a later
    task) must parse `result.content[0].text` as JSON to get a list of these. This model
    itself just represents one already-parsed entry.
    """

    model_config = ConfigDict(extra="ignore")

    question: str
    answer: str


class CartLine(BaseModel):
    """One line item on a cart. NOT empirically confirmed from a real response
    (docs/SHOPIFY_NOTES.md, "Cart response shape") -- inferred from the update_cart
    INPUT schema's `cart.line_items[].{id, quantity, item.id}` shape. Kept intentionally
    loose; `raw` is the safety net if the real response shape differs.
    """

    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    quantity: int | None = None
    variant_id: str | None = None
    raw: dict = Field(default_factory=dict)


class ShopCart(BaseModel):
    """A Shopify cart, from get_cart/create_cart/update_cart (spec section 5.1.3). NOT
    empirically confirmed (see CartLine docstring and docs/SHOPIFY_NOTES.md) -- treat
    every field as best-effort until spot-checked against a real response.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    checkout_url: str | None = None
    lines: list[CartLine] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)
