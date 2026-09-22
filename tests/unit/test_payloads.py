"""Tests for protocol/payloads.py -- all 14 model classes.

Tests cover:
- Round-trip serialization/deserialization for each model
- Extra field rejection (extra="forbid" active)
- Model-specific validation rules and constraints
"""

import pytest
from pydantic import ValidationError

from bigbrain.protocol.payloads import (
    Category,
    CheckoutReady,
    CheckoutRequest,
    Counter,
    Failure,
    HardConstraints,
    Intent,
    Item,
    Offer,
    Provenance,
    Shop,
    ShopText,
    SoftPreference,
    Terms,
)

# ============================================================================
# Category Tests
# ============================================================================


def test_category_round_trip():
    """Test Category serialization and deserialization."""
    original = Category(
        taxonomy="shopify",
        id="gid://shopify/Collection/123456",
        google_id="google_category_id_456",
    )
    json_str = original.model_dump_json()
    restored = Category.model_validate_json(json_str)
    assert restored == original


def test_category_extra_field_rejected():
    """Test that Category rejects extra fields."""
    with pytest.raises(ValidationError):
        Category(
            taxonomy="shopify",
            id="gid://shopify/Collection/123456",
            extra_field="should_fail",
        )


# ============================================================================
# HardConstraints Tests
# ============================================================================


def test_hardconstraints_round_trip():
    """Test HardConstraints serialization and deserialization."""
    original = HardConstraints(
        max_price_minor=50000,
        currency="USD",
        ship_to_country="US",
        condition=["new", "refurbished"],
        must_have={"color": "black"},
    )
    json_str = original.model_dump_json()
    restored = HardConstraints.model_validate_json(json_str)
    assert restored == original


def test_hardconstraints_extra_field_rejected():
    """Test that HardConstraints rejects extra fields."""
    with pytest.raises(ValidationError):
        HardConstraints(
            max_price_minor=50000,
            currency="USD",
            ship_to_country="US",
            unexpected_field="fail",
        )


def test_hardconstraints_max_price_zero_rejected():
    """Test that max_price_minor=0 is rejected (must be > 0)."""
    with pytest.raises(ValidationError):
        HardConstraints(
            max_price_minor=0,
            currency="USD",
            ship_to_country="US",
        )


def test_hardconstraints_max_price_negative_rejected():
    """Test that max_price_minor negative is rejected (must be > 0)."""
    with pytest.raises(ValidationError):
        HardConstraints(
            max_price_minor=-100,
            currency="USD",
            ship_to_country="US",
        )


# ============================================================================
# SoftPreference Tests
# ============================================================================


def test_softpreference_round_trip():
    """Test SoftPreference serialization and deserialization."""
    original = SoftPreference(weight=0.3, ideal=2.0, worst=10.0)
    json_str = original.model_dump_json()
    restored = SoftPreference.model_validate_json(json_str)
    assert restored == original


def test_softpreference_extra_field_rejected():
    """Test that SoftPreference rejects extra fields."""
    with pytest.raises(ValidationError):
        SoftPreference(weight=0.3, ideal=2.0, worst=10.0, extra_param="fail")


# ============================================================================
# Intent Tests
# ============================================================================


def test_intent_round_trip():
    """Test Intent serialization and deserialization (headphones example from spec)."""
    original = Intent(
        category=Category(taxonomy="shopify", id="gid://shopify/Collection/headphones"),
        keywords=["bluetooth", "noise-cancelling"],
        hard_constraints=HardConstraints(
            max_price_minor=30000,
            currency="USD",
            ship_to_country="US",
        ),
        soft_preferences={
            "delivery_days": SoftPreference(weight=0.2, ideal=2, worst=10),
            "return_days": SoftPreference(weight=0.1, ideal=30, worst=0),
        },
        reply_to="intent-reply-address",
        reply_pubkey="ephemeral-public-key-base64",
        deadline="2025-01-15T18:00:00Z",
        max_rounds=3,
    )
    json_str = original.model_dump_json()
    restored = Intent.model_validate_json(json_str)
    assert restored == original


def test_intent_extra_field_rejected():
    """Test that Intent rejects extra fields."""
    with pytest.raises(ValidationError):
        Intent(
            category=Category(taxonomy="shopify", id="gid://shopify/Collection/test"),
            keywords=[],
            hard_constraints=HardConstraints(
                max_price_minor=30000, currency="USD", ship_to_country="US"
            ),
            soft_preferences={},
            reply_to="test-reply",
            reply_pubkey="test-key",
            deadline="2025-01-15T18:00:00Z",
            max_rounds=0,
            unexpected_field="fail",
        )


def test_intent_max_rounds_negative_rejected():
    """Test that Intent rejects negative max_rounds."""
    with pytest.raises(ValidationError):
        Intent(
            category=Category(taxonomy="shopify", id="gid://shopify/Collection/test"),
            keywords=[],
            hard_constraints=HardConstraints(
                max_price_minor=30000, currency="USD", ship_to_country="US"
            ),
            soft_preferences={},
            reply_to="test-reply",
            reply_pubkey="test-key",
            deadline="2025-01-15T18:00:00Z",
            max_rounds=-1,
        )


def test_intent_multiple_soft_preferences():
    """Test Intent with multiple soft_preferences keys."""
    original = Intent(
        category=Category(taxonomy="shopify", id="gid://shopify/Collection/test"),
        keywords=["laptop"],
        hard_constraints=HardConstraints(
            max_price_minor=150000, currency="USD", ship_to_country="US"
        ),
        soft_preferences={
            "delivery_days": SoftPreference(weight=0.2, ideal=2, worst=10),
            "return_days": SoftPreference(weight=0.1, ideal=30, worst=0),
            "warranty_months": SoftPreference(weight=0.15, ideal=24, worst=0),
        },
        reply_to="reply-addr",
        reply_pubkey="pubkey",
        deadline="2025-02-01T10:00:00Z",
        max_rounds=5,
    )
    json_str = original.model_dump_json()
    restored = Intent.model_validate_json(json_str)
    assert restored == original
    assert len(restored.soft_preferences) == 3
    assert "delivery_days" in restored.soft_preferences
    assert "return_days" in restored.soft_preferences
    assert "warranty_months" in restored.soft_preferences


# ============================================================================
# Shop Tests
# ============================================================================


def test_shop_round_trip():
    """Test Shop serialization and deserialization."""
    original = Shop(domain="example.myshopify.com", display_name="Example Shop")
    json_str = original.model_dump_json()
    restored = Shop.model_validate_json(json_str)
    assert restored == original


def test_shop_extra_field_rejected():
    """Test that Shop rejects extra fields."""
    with pytest.raises(ValidationError):
        Shop(
            domain="example.myshopify.com",
            display_name="Example Shop",
            extra_field="fail",
        )


# ============================================================================
# Item Tests
# ============================================================================


def test_item_round_trip():
    """Test Item serialization and deserialization."""
    original = Item(
        product_id="gid://shopify/Product/123456",
        variant_id="gid://shopify/ProductVariant/7890",
        title="Sony WH-1000XM4 Headphones",
        options={"color": "black", "size": "one-size"},
        url="https://example.myshopify.com/products/headphones",
    )
    json_str = original.model_dump_json()
    restored = Item.model_validate_json(json_str)
    assert restored == original


def test_item_extra_field_rejected():
    """Test that Item rejects extra fields."""
    with pytest.raises(ValidationError):
        Item(
            product_id="gid://shopify/Product/123456",
            variant_id="gid://shopify/ProductVariant/7890",
            title="Sony Headphones",
            options={},
            url="https://example.com/products",
            extra_field="fail",
        )


# ============================================================================
# Terms Tests
# ============================================================================


def test_terms_round_trip():
    """Test Terms serialization and deserialization."""
    original = Terms(
        price_minor=27999,
        currency="USD",
        available=True,
        shipping_cost_minor=0,
        delivery_days_estimate=3,
        return_days=30,
        warranty_months=12,
        negotiable=None,
    )
    json_str = original.model_dump_json()
    restored = Terms.model_validate_json(json_str)
    assert restored == original


def test_terms_extra_field_rejected():
    """Test that Terms rejects extra fields."""
    with pytest.raises(ValidationError):
        Terms(
            price_minor=27999,
            currency="USD",
            extra_field="fail",
        )


def test_terms_all_none_default():
    """Test Terms() constructs with all fields None."""
    original = Terms()
    assert original.price_minor is None
    assert original.currency is None
    assert original.available is None
    assert original.shipping_cost_minor is None
    assert original.delivery_days_estimate is None
    assert original.return_days is None
    assert original.warranty_months is None
    assert original.negotiable is None
    # Round-trip test
    json_str = original.model_dump_json()
    restored = Terms.model_validate_json(json_str)
    assert restored == original


# ============================================================================
# Provenance Tests
# ============================================================================


def test_provenance_round_trip():
    """Test Provenance serialization and deserialization."""
    original = Provenance(
        tool="shopify_storefront_api",
        fetched_at="2025-01-15T12:00:00Z",
        ref="gid://shopify/ProductVariant/7890",
        excerpt_hash=None,
    )
    json_str = original.model_dump_json()
    restored = Provenance.model_validate_json(json_str)
    assert restored == original


def test_provenance_extra_field_rejected():
    """Test that Provenance rejects extra fields."""
    with pytest.raises(ValidationError):
        Provenance(
            tool="shopify_storefront_api",
            fetched_at="2025-01-15T12:00:00Z",
            extra_field="fail",
        )


# ============================================================================
# ShopText Tests
# ============================================================================


def test_shoptext_round_trip():
    """Test ShopText serialization and deserialization."""
    original = ShopText(
        title="Premium Wireless Headphones",
        description_snippet="High-quality noise-cancelling headphones with 30-hour battery.",
        untrusted=True,
    )
    json_str = original.model_dump_json()
    restored = ShopText.model_validate_json(json_str)
    assert restored == original


def test_shoptext_extra_field_rejected():
    """Test that ShopText rejects extra fields."""
    with pytest.raises(ValidationError):
        ShopText(
            title="Test Title",
            description_snippet="Test description",
            untrusted=True,
            extra_field="fail",
        )


def test_shoptext_untrusted_false_rejected():
    """Test that ShopText rejects untrusted=False (must be Literal[True])."""
    with pytest.raises(ValidationError):
        ShopText(
            title="Test Title",
            description_snippet="Test description",
            untrusted=False,
        )


def test_shoptext_untrusted_default():
    """Test that ShopText untrusted defaults to True."""
    original = ShopText(
        title="Test Title",
        description_snippet="Test description",
    )
    assert original.untrusted is True


# ============================================================================
# Offer Tests
# ============================================================================


def test_offer_round_trip():
    """Test Offer serialization and deserialization ($279.99 example from spec)."""
    original = Offer(
        offer_id="offer-001",
        offer_version=1,
        representation="Sony WH-1000XM4",
        shop=Shop(
            domain="example.myshopify.com",
            display_name="Example Shop",
        ),
        item=Item(
            product_id="gid://shopify/Product/123456",
            variant_id="gid://shopify/ProductVariant/7890",
            title="Sony WH-1000XM4 Headphones",
            options={"color": "black"},
            url="https://example.myshopify.com/products/headphones",
        ),
        terms=Terms(
            price_minor=27999,
            currency="USD",
            available=True,
            shipping_cost_minor=0,
            delivery_days_estimate=3,
            return_days=30,
            warranty_months=12,
            negotiable=None,
        ),
        provenance={
            "price": Provenance(
                tool="shopify_storefront_api",
                fetched_at="2025-01-15T12:00:00Z",
                ref="gid://shopify/ProductVariant/7890",
            )
        },
        valid_until="2025-01-16T12:00:00Z",
        shop_text=ShopText(
            title="Premium Wireless Headphones",
            description_snippet="High-quality headphones.",
            untrusted=True,
        ),
    )
    json_str = original.model_dump_json()
    restored = Offer.model_validate_json(json_str)
    assert restored == original


def test_offer_extra_field_rejected():
    """Test that Offer rejects extra fields."""
    with pytest.raises(ValidationError):
        Offer(
            offer_id="offer-001",
            offer_version=1,
            representation="Test",
            shop=Shop(domain="test.com", display_name="Test"),
            item=Item(
                product_id="p1",
                variant_id="v1",
                title="Test Item",
                options={},
                url="https://test.com",
            ),
            terms=Terms(),
            provenance={},
            valid_until="2025-01-16T12:00:00Z",
            shop_text=ShopText(title="Title", description_snippet="Desc"),
            extra_field="fail",
        )


def test_offer_version_zero_rejected():
    """Test that Offer rejects offer_version=0 (must be >= 1)."""
    with pytest.raises(ValidationError):
        Offer(
            offer_id="offer-001",
            offer_version=0,
            representation="Test",
            shop=Shop(domain="test.com", display_name="Test"),
            item=Item(
                product_id="p1",
                variant_id="v1",
                title="Test Item",
                options={},
                url="https://test.com",
            ),
            terms=Terms(),
            provenance={},
            valid_until="2025-01-16T12:00:00Z",
            shop_text=ShopText(title="Title", description_snippet="Desc"),
        )


def test_offer_initial_and_revised():
    """Test Offer initial (version=1, negotiable=None) and revised (version=2, negotiable=False)."""
    # Initial offer
    initial = Offer(
        offer_id="offer-001",
        offer_version=1,
        representation="Sony WH-1000XM4",
        shop=Shop(domain="shop.com", display_name="Shop"),
        item=Item(
            product_id="p1",
            variant_id="v1",
            title="Headphones",
            options={},
            url="https://shop.com/product",
        ),
        terms=Terms(
            price_minor=27999,
            currency="USD",
            negotiable=None,
        ),
        provenance={},
        valid_until="2025-01-16T12:00:00Z",
        shop_text=ShopText(title="Title", description_snippet="Desc"),
    )

    # Revised offer with same offer_id, bumped version, negotiable=False
    revised = Offer(
        offer_id="offer-001",
        offer_version=2,
        representation="Sony WH-1000XM4",
        shop=Shop(domain="shop.com", display_name="Shop"),
        item=Item(
            product_id="p1",
            variant_id="v1",
            title="Headphones",
            options={},
            url="https://shop.com/product",
        ),
        terms=Terms(
            price_minor=27999,
            currency="USD",
            negotiable=False,
        ),
        provenance={},
        valid_until="2025-01-16T12:00:00Z",
        shop_text=ShopText(title="Title", description_snippet="Desc"),
    )

    assert initial.offer_id == revised.offer_id
    assert initial.offer_version == 1
    assert revised.offer_version == 2
    assert initial.terms.negotiable is None
    assert revised.terms.negotiable is False


# ============================================================================
# Counter Tests
# ============================================================================


def test_counter_round_trip():
    """Test Counter serialization and deserialization."""
    original = Counter(
        offer_id="offer-001",
        target_offer_version=1,
        asks={"price_minor": 25000, "delivery_days": 2},
        alternatives_ok=False,
    )
    json_str = original.model_dump_json()
    restored = Counter.model_validate_json(json_str)
    assert restored == original


def test_counter_extra_field_rejected():
    """Test that Counter rejects extra fields."""
    with pytest.raises(ValidationError):
        Counter(
            offer_id="offer-001",
            target_offer_version=1,
            asks={},
            alternatives_ok=True,
            extra_field="fail",
        )


def test_counter_target_offer_version_zero_rejected():
    """Test that Counter rejects target_offer_version=0 (must be >= 1)."""
    with pytest.raises(ValidationError):
        Counter(
            offer_id="offer-001",
            target_offer_version=0,
            asks={},
            alternatives_ok=True,
        )


# ============================================================================
# CheckoutRequest Tests
# ============================================================================


def test_checkoutrequest_round_trip():
    """Test CheckoutRequest serialization and deserialization."""
    original = CheckoutRequest(
        offer_id="offer-001",
        offer_version=1,
        terms_hash="sha256-hash-of-terms",
        quantity=2,
        approval_proof="signature-proof-base64",
    )
    json_str = original.model_dump_json()
    restored = CheckoutRequest.model_validate_json(json_str)
    assert restored == original


def test_checkoutrequest_extra_field_rejected():
    """Test that CheckoutRequest rejects extra fields."""
    with pytest.raises(ValidationError):
        CheckoutRequest(
            offer_id="offer-001",
            offer_version=1,
            terms_hash="hash",
            quantity=1,
            approval_proof="proof",
            extra_field="fail",
        )


def test_checkoutrequest_quantity_zero_rejected():
    """Test that CheckoutRequest rejects quantity=0 (must be >= 1)."""
    with pytest.raises(ValidationError):
        CheckoutRequest(
            offer_id="offer-001",
            offer_version=1,
            terms_hash="hash",
            quantity=0,
            approval_proof="proof",
        )


# ============================================================================
# CheckoutReady Tests
# ============================================================================


def test_checkoutready_round_trip():
    """Test CheckoutReady serialization and deserialization."""
    original = CheckoutReady(
        checkout_url="https://example.myshopify.com/checkout/session-id",
        terms=Terms(
            price_minor=27999,
            currency="USD",
            available=True,
            shipping_cost_minor=0,
            delivery_days_estimate=3,
            return_days=30,
            warranty_months=12,
            negotiable=None,
        ),
        terms_hash="sha256-hash-of-verified-terms",
    )
    json_str = original.model_dump_json()
    restored = CheckoutReady.model_validate_json(json_str)
    assert restored == original


def test_checkoutready_extra_field_rejected():
    """Test that CheckoutReady rejects extra fields."""
    with pytest.raises(ValidationError):
        CheckoutReady(
            checkout_url="https://example.com/checkout",
            terms=Terms(),
            terms_hash="hash",
            extra_field="fail",
        )


# ============================================================================
# Failure Tests
# ============================================================================


def test_failure_round_trip():
    """Test Failure serialization and deserialization."""
    original = Failure(
        reason="out_of_stock",
        new_terms=None,
    )
    json_str = original.model_dump_json()
    restored = Failure.model_validate_json(json_str)
    assert restored == original


def test_failure_extra_field_rejected():
    """Test that Failure rejects extra fields."""
    with pytest.raises(ValidationError):
        Failure(
            reason="test_reason",
            new_terms=None,
            extra_field="fail",
        )


def test_failure_terms_changed_with_new_terms():
    """Test Failure with reason='terms_changed' and new_terms set."""
    original = Failure(
        reason="terms_changed",
        new_terms=Terms(price_minor=32000, currency="USD"),
    )
    assert original.reason == "terms_changed"
    assert original.new_terms is not None
    assert original.new_terms.price_minor == 32000

    # Round-trip test
    json_str = original.model_dump_json()
    restored = Failure.model_validate_json(json_str)
    assert restored == original


def test_failure_bare_reason_no_terms():
    """Test Failure with reason and no new_terms (new_terms=None default)."""
    original = Failure(reason="no_matching_variant")
    assert original.reason == "no_matching_variant"
    assert original.new_terms is None

    # Round-trip test
    json_str = original.model_dump_json()
    restored = Failure.model_validate_json(json_str)
    assert restored == original
