"""Tests for Shopify models (M2, spec section 5.1.3).

Tests parse REAL Shopify API responses captured live in
tests/unit/data/shopify_live_samples/ to verify model shape and lenient parsing.
"""

import json
from pathlib import Path

from bigbrain.shopify.models import (
    Availability,
    CartLine,
    Description,
    MediaItem,
    Money,
    PriceRange,
    ShopCart,
    ShopPolicyAnswer,
    ShopProduct,
    ShopVariant,
    TaxonomyCategory,
    VariantOption,
)

# Path to real sample data
SAMPLES_DIR = Path(__file__).parent / "data" / "shopify_live_samples"


class TestSearchCatalogParsing:
    """Test 1: Parse real search_catalog response."""

    def test_parse_first_product_from_search_catalog(self):
        """Parse first product, verify shape (esp. html vs plain description)."""
        with open(SAMPLES_DIR / "search_catalog_response.json") as f:
            data = json.load(f)

        products = data["result"]["structuredContent"]["products"]
        assert len(products) > 0, "No products in search_catalog response"

        first_product = products[0]
        product = ShopProduct.model_validate(first_product)

        # Assertions per requirement 1
        assert product.id.startswith("gid://shopify/Product/"), (
            f"Expected product id to start with gid://shopify/Product/, got {product.id}"
        )
        assert product.title and len(product.title) > 0, "Expected non-empty title"
        assert product.description is not None, "Expected description to be present"
        assert product.description.html and len(product.description.html) > 0, (
            "Expected non-empty description.html (storefront catalog uses html, not plain)"
        )
        assert product.description.plain is None, (
            "Expected description.plain to be None on storefront catalog"
        )
        assert product.price_range is not None, "Expected price_range to be present"
        assert product.price_range.min is not None, "Expected price_range.min to be present"
        assert isinstance(product.price_range.min.amount, int), (
            "Expected price_range.min.amount to be int"
        )
        assert product.price_range.min.currency and len(product.price_range.min.currency) > 0, (
            "Expected non-empty currency"
        )
        assert len(product.variants) > 0, "Expected at least one variant"

        first_variant = product.variants[0]
        assert first_variant.price is not None, "Expected variant price to be present"
        assert isinstance(first_variant.price.amount, int), (
            "Expected variant price.amount to be int"
        )
        assert first_variant.availability is not None, "Expected variant availability to be present"
        assert isinstance(first_variant.availability.available, bool), (
            "Expected variant availability.available to be bool"
        )

        assert len(product.categories) > 0, "Expected at least one category"
        for cat in product.categories:
            assert cat.value and cat.value.startswith("gid://shopify/TaxonomyCategory/"), (
                f"Expected category.value to start with "
                f"gid://shopify/TaxonomyCategory/, got {cat.value}"
            )

    def test_parse_all_products_in_search_catalog(self):
        """Test 2: Parse EVERY product in search_catalog, not just first."""
        with open(SAMPLES_DIR / "search_catalog_response.json") as f:
            data = json.load(f)

        products = data["result"]["structuredContent"]["products"]
        assert len(products) > 0, "No products in search_catalog response"

        for product_data in products:
            product = ShopProduct.model_validate(product_data)
            assert product.id and len(product.id) > 0, "Expected non-empty product id"

    def test_extra_fields_dont_raise(self):
        """Test 3: Extra fields (tags, collections) don't raise on model_validate."""
        with open(SAMPLES_DIR / "search_catalog_response.json") as f:
            data = json.load(f)

        products = data["result"]["structuredContent"]["products"]
        first_product = products[0]

        # Verify the raw data has tags and collections (fields not in model)
        assert "tags" in first_product, "Expected 'tags' in raw product data"
        assert "collections" in first_product, "Expected 'collections' in raw product data"

        # Model should parse without raising despite extra keys
        product = ShopProduct.model_validate(first_product)
        assert product.id, "Expected product to parse successfully"


class TestGetProductParsing:
    """Test 4: Parse real get_product response."""

    def test_parse_get_product_response(self):
        """Parse single product from get_product, verify it matches expected id."""
        with open(SAMPLES_DIR / "get_product_response.json") as f:
            data = json.load(f)

        product_data = data["result"]["structuredContent"]["product"]
        product = ShopProduct.model_validate(product_data)

        assert product.id, "Expected product id to be present"
        assert product.id.startswith("gid://shopify/Product/"), (
            f"Expected product id to start with gid://shopify/Product/, got {product.id}"
        )


class TestSearchPoliciesParsing:
    """Test 5: Parse real search_shop_policies_and_faqs response."""

    def test_parse_policies_from_content_text(self):
        """Test 5: Parse policies from content[0].text JSON, verify no structuredContent."""
        with open(SAMPLES_DIR / "search_policies_response.json") as f:
            data = json.load(f)

        result = data["result"]

        # Requirement: structuredContent must NOT be present
        assert "structuredContent" not in result, (
            "Expected search_policies response to NOT have structuredContent field"
        )

        # Parse the JSON string from content[0].text
        assert "content" in result, "Expected 'content' in result"
        assert len(result["content"]) > 0, "Expected at least one content item"

        content_text = result["content"][0]["text"]
        policies = json.loads(content_text)

        assert isinstance(policies, list), "Expected content[0].text to parse as a list"
        assert len(policies) >= 2, "Expected at least 2 policies"

        # Build ShopPolicyAnswer from each entry
        for policy_data in policies:
            answer = ShopPolicyAnswer.model_validate(policy_data)
            assert answer.question and len(answer.question) > 0, "Expected non-empty question"
            assert answer.answer and len(answer.answer) > 0, "Expected non-empty answer"


class TestMoneyRoundTrip:
    """Test 6: Money model round-trip."""

    def test_money_round_trip(self):
        """Test that Money(amount=11000, currency='USD').model_dump() works."""
        money = Money(amount=11000, currency="USD")
        dumped = money.model_dump()

        assert dumped == {
            "amount": 11000,
            "currency": "USD",
        }, f"Expected exact match, got {dumped}"


class TestMinimalConstruction:
    """Test 7: Minimal construction with only required fields."""

    def test_money_minimal(self):
        """Money with only required fields."""
        money = Money(amount=100, currency="USD")
        assert money.amount == 100
        assert money.currency == "USD"

    def test_description_minimal(self):
        """Description with no required fields (all optional)."""
        desc = Description()
        assert desc.html is None
        assert desc.plain is None

    def test_media_item_minimal(self):
        """MediaItem with no required fields."""
        media = MediaItem()
        assert media.type is None
        assert media.url is None

    def test_variant_option_minimal(self):
        """VariantOption with no required fields."""
        opt = VariantOption()
        assert opt.name is None
        assert opt.label is None

    def test_availability_minimal(self):
        """Availability with no required fields."""
        avail = Availability()
        assert avail.available is None

    def test_price_range_minimal(self):
        """PriceRange with no required fields."""
        pr = PriceRange()
        assert pr.min is None
        assert pr.max is None

    def test_taxonomy_category_minimal(self):
        """TaxonomyCategory with no required fields."""
        cat = TaxonomyCategory()
        assert cat.value is None
        assert cat.taxonomy is None

    def test_shop_variant_minimal(self):
        """ShopVariant with only required field (id)."""
        variant = ShopVariant(id="x")
        assert variant.id == "x"
        assert variant.sku is None
        assert variant.title is None
        assert variant.price is None
        assert variant.options == []
        assert variant.media == []
        assert variant.raw == {}

    def test_shop_product_minimal(self):
        """ShopProduct with only required field (id)."""
        product = ShopProduct(id="x")
        assert product.id == "x"
        assert product.title is None
        assert product.variants == []
        assert product.media == []
        assert product.categories == []
        assert product.raw == {}

    def test_shop_policy_answer_minimal(self):
        """ShopPolicyAnswer with required fields."""
        answer = ShopPolicyAnswer(question="q", answer="a")
        assert answer.question == "q"
        assert answer.answer == "a"

    def test_cart_line_minimal(self):
        """CartLine with no required fields."""
        line = CartLine()
        assert line.id is None
        assert line.quantity is None
        assert line.variant_id is None
        assert line.raw == {}

    def test_shop_cart_minimal(self):
        """ShopCart with only required field (id)."""
        cart = ShopCart(id="x")
        assert cart.id == "x"
        assert cart.checkout_url is None
        assert cart.lines == []
        assert cart.raw == {}


class TestEmptyCollections:
    """Test 8: ShopProduct with empty lists still parses."""

    def test_empty_variants_categories_media(self):
        """ShopProduct with just id has empty lists for variants/categories/media."""
        product = ShopProduct(id="x")
        assert product.variants == []
        assert product.categories == []
        assert product.media == []
