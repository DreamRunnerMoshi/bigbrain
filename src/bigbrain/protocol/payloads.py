"""Inner payloads (BIGBRAIN_SPEC.md section 6.2) -- what's inside an Envelope's
ciphertext once decrypted. Money is always integer minor units (spec section 4, UCP
catalog convention: $6.00 == 600). Unknown/unverified terms are `None`, never guessed
(spec section 6.2) -- scorers must treat `None` as worst-case, not as zero.

See docs/DECISIONS.md ADR-006 for two decisions this module makes beyond the spec's
literal example JSON: the CheckoutReady/Failure split (mapped 1:1 to envelope
type=CHECKOUT_READY / type=FAILURE), and why there is no separate "RevisedOffer" class
(a shadow agent's revision is just another Offer with a bumped offer_version).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Category(BaseModel):
    """Channel-routing category. `taxonomy` is "shopify" for now (ADR-001); "google" is
    reserved for future non-Shopify merchants.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    taxonomy: str
    id: str
    google_id: str | None = None


class HardConstraints(BaseModel):
    """Must-satisfy filters. An offer that violates any of these scores zero (spec
    section 6.3).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    max_price_minor: int = Field(gt=0)
    currency: str
    ship_to_country: str
    condition: list[str] = Field(default_factory=list)
    must_have: dict[str, str] = Field(default_factory=dict)


class SoftPreference(BaseModel):
    """One weighted linear preference: utility interpolates linearly between `worst`
    (utility 0) and `ideal` (utility 1) for this attribute (spec section 6.3).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    weight: float = Field(ge=0)
    ideal: float
    worst: float


class Intent(BaseModel):
    """The CFP payload. `reply_to`/`reply_pubkey` let a BigBrainShop answer directly
    without ever learning the buyer's persistent identity -- both are per-session
    ephemeral (spec section 6.5). `soft_preferences` is keyed by attribute name, e.g.
    "delivery_days", "return_days", "shipping_cost_minor".
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    category: Category
    keywords: list[str] = Field(default_factory=list)
    hard_constraints: HardConstraints
    soft_preferences: dict[str, SoftPreference] = Field(default_factory=dict)
    reply_to: str
    reply_pubkey: str
    deadline: str
    max_rounds: int = Field(ge=0)


class Shop(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    domain: str
    display_name: str


class Item(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    product_id: str
    variant_id: str
    title: str
    options: dict[str, str] = Field(default_factory=dict)
    url: str


class Terms(BaseModel):
    """Every field is `None` when unknown -- never guessed (spec section 6.2).
    `negotiable` is only meaningful on a revised offer (ADR-006): `False` means a
    shadow agent is re-stating the same terms because no better-fitting variant/product
    exists; `None` on a first offer, where the concept doesn't apply yet.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    price_minor: int | None = None
    currency: str | None = None
    available: bool | None = None
    shipping_cost_minor: int | None = None
    delivery_days_estimate: int | None = None
    return_days: int | None = None
    warranty_months: int | None = None
    negotiable: bool | None = None


class Provenance(BaseModel):
    """One term's evidence trail (I9: every offer term traces to real Shopify data
    fetched within the freshness window). `ref` is used for catalog-sourced terms
    (e.g. a variant_id); `excerpt_hash` for policy-text-sourced terms.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    tool: str
    fetched_at: str
    ref: str | None = None
    excerpt_hash: str | None = None


class ShopText(BaseModel):
    """Untrusted free text straight from Shopify -- shown to the human, never used for
    decisions (spec section 8.5, defense D1 "structured-only"). Always untrusted by
    construction, hence the `Literal[True]` rather than a plain bool default.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    title: str
    description_snippet: str
    untrusted: Literal[True] = True


class Offer(BaseModel):
    """The PROPOSE payload, sealed to the buyer's reply_pubkey (spec section 6.5:
    SealedBox). `offer_id` stays fixed across a negotiation; `offer_version` increments
    on every revision from the same shadow agent (ADR-006 -- there is no separate
    RevisedOffer class, a revision is just a new Offer with a bumped offer_version and,
    for a same-terms restatement, `terms.negotiable = False`).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    offer_id: str
    offer_version: int = Field(ge=1)
    representation: str
    shop: Shop
    item: Item
    terms: Terms
    provenance: dict[str, Provenance] = Field(default_factory=dict)
    valid_until: str
    shop_text: ShopText


class Counter(BaseModel):
    """Private counter from the buyer to one agent -- never leaks another agent's
    terms (I5)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    offer_id: str
    target_offer_version: int = Field(ge=1)
    asks: dict[str, float] = Field(default_factory=dict)
    alternatives_ok: bool = True


class CheckoutRequest(BaseModel):
    """Buyer -> winning agent, after human approval (I1). `approval_proof` is a
    signature over (offer_id, offer_version, terms_hash, quantity) with the human's
    device key -- checked before any cart is created. Envelope type=CHECKOUT_REQUEST.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    offer_id: str
    offer_version: int = Field(ge=1)
    terms_hash: str
    quantity: int = Field(ge=1)
    approval_proof: str


class CheckoutReady(BaseModel):
    """Agent -> buyer after a successful re-verification (I10): a working checkout URL
    with re-verified terms. Envelope type=CHECKOUT_READY. (If terms changed since
    approval instead, the agent sends envelope type=FAILURE with a Failure payload --
    see ADR-006.)
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    checkout_url: str
    terms: Terms
    terms_hash: str


class Failure(BaseModel):
    """Generic FAILURE payload (envelope type=FAILURE). `reason="terms_changed"` with
    `new_terms` set is I10's re-verification-changed-something case (ADR-006); other
    reasons are free text for now.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    reason: str
    new_terms: Terms | None = None
