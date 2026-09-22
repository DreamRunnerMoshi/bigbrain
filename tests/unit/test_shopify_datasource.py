"""Tests for ShopDataSource, LiveShopify, and ReplayShopify (M2 milestone).
All tests are fully offline using respx to mock HTTP calls; no real network access
or API keys required.
"""

import json

import pytest
import respx
from httpx import Response

from bigbrain.shopify.datasource import (
    FixtureNotFoundError,
    LiveShopify,
    ReplayShopify,
)
from bigbrain.shopify.models import ShopPolicyAnswer, ShopProduct


@pytest.fixture
def search_catalog_fixture():
    """Load real search_catalog response fixture."""
    with open("tests/unit/data/shopify_live_samples/search_catalog_response.json") as f:
        return json.load(f)


@pytest.fixture
def get_product_fixture():
    """Load real get_product response fixture."""
    with open("tests/unit/data/shopify_live_samples/get_product_response.json") as f:
        return json.load(f)


@pytest.fixture
def search_policies_fixture():
    """Load real search_policies response fixture."""
    with open("tests/unit/data/shopify_live_samples/search_policies_response.json") as f:
        return json.load(f)


# Test 1: Round trip via a real client recording, then replaying
@pytest.mark.asyncio
async def test_round_trip_record_then_replay_search_catalog(tmp_path, search_catalog_fixture):
    """Use respx to mock a search_catalog call through a real ShopifyMCPClient
    constructed with record_path, then replay through ReplayShopify.
    Assert the replayed result matches the live-mocked result.
    """
    from bigbrain.shopify.client import ShopifyMCPClient

    cassette_path = tmp_path / "test-shop.example.com" / "cassette.jsonl"
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        record_path=cassette_path,
    )

    try:
        # Mock the search_catalog call
        structured = search_catalog_fixture["result"]["structuredContent"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": structured,
        }

        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Make the live client call to populate the cassette
            live_products, live_pagination = await client.search_catalog(query="wool runner shoes")

            # Assert we got products from the live call
            assert isinstance(live_products, list)
            assert len(live_products) > 0
            assert all(isinstance(p, ShopProduct) for p in live_products)

        # Now replay through ReplayShopify
        replay = ReplayShopify(tmp_path, "test-shop.example.com")
        replay_products, replay_pagination = await replay.search_catalog(query="wool runner shoes")

        # Assert the replayed result matches the live result
        assert len(replay_products) == len(live_products)
        for i, (live_p, replay_p) in enumerate(zip(live_products, replay_products, strict=True)):
            assert replay_p.id == live_p.id, f"product {i}: id mismatch"
            if live_p.description and live_p.description.html:
                assert replay_p.description.html == live_p.description.html

    finally:
        await client.aclose()


# Test 2: Missing cassette file
@pytest.mark.asyncio
async def test_missing_cassette_raises_fixture_not_found(tmp_path):
    """Constructing ReplayShopify with a non-existent cassette must NOT raise.
    But calling any method on it raises FixtureNotFoundError."""
    replay = ReplayShopify(tmp_path, "no-such-shop.example.com")

    # Construction succeeds
    assert replay.shop_domain == "no-such-shop.example.com"

    # But calling any method raises FixtureNotFoundError
    with pytest.raises(FixtureNotFoundError) as exc_info:
        await replay.search_catalog(query="x")

    assert exc_info.value.shop_domain == "no-such-shop.example.com"
    assert exc_info.value.tool == "search_catalog"


# Test 3: Recorded call with different arguments doesn't match
@pytest.mark.asyncio
async def test_different_arguments_no_match(tmp_path, search_catalog_fixture):
    """Record a search_catalog(query="wool runner shoes") call, then try to
    replay with a different query. Should raise FixtureNotFoundError."""
    from bigbrain.shopify.client import ShopifyMCPClient

    cassette_path = tmp_path / "test-shop.example.com" / "cassette.jsonl"
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        record_path=cassette_path,
    )

    try:
        structured = search_catalog_fixture["result"]["structuredContent"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": structured,
        }

        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Record with specific query
            await client.search_catalog(query="wool runner shoes")

        # Try to replay with different query
        replay = ReplayShopify(tmp_path, "test-shop.example.com")
        with pytest.raises(FixtureNotFoundError):
            await replay.search_catalog(query="something completely different")

    finally:
        await client.aclose()


# Test 4: get_product round trip
@pytest.mark.asyncio
async def test_round_trip_get_product(tmp_path, get_product_fixture):
    """Record a get_product call, replay it, assert the product IDs match."""
    from bigbrain.shopify.client import ShopifyMCPClient

    cassette_path = tmp_path / "test-shop.example.com" / "cassette.jsonl"
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        record_path=cassette_path,
    )

    try:
        real_product_id = get_product_fixture["result"]["structuredContent"]["product"]["id"]
        structured = get_product_fixture["result"]["structuredContent"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": structured,
        }

        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Record the call
            live_product = await client.get_product(real_product_id)

        # Replay the call
        replay = ReplayShopify(tmp_path, "test-shop.example.com")
        replay_product = await replay.get_product(real_product_id)

        # Assert IDs match
        assert replay_product.id == live_product.id

    finally:
        await client.aclose()


# Test 5: search_policies round trip
@pytest.mark.asyncio
async def test_round_trip_search_policies(tmp_path, search_policies_fixture):
    """Record a search_policies call, replay it, assert list counts and content match."""
    from bigbrain.shopify.client import ShopifyMCPClient

    cassette_path = tmp_path / "test-shop.example.com" / "cassette.jsonl"
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        record_path=cassette_path,
    )

    try:
        result = search_policies_fixture["result"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": result,
        }

        with respx.mock:
            respx.post("https://test-shop.example.com/api/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Record the call
            live_answers = await client.search_policies("what is your return policy")

        # Replay the call
        replay = ReplayShopify(tmp_path, "test-shop.example.com")
        replay_answers = await replay.search_policies("what is your return policy")

        # Assert counts match
        assert len(replay_answers) == len(live_answers)

        # Assert all answers have matching content
        for i, (live_a, replay_a) in enumerate(zip(live_answers, replay_answers, strict=True)):
            assert isinstance(replay_a, ShopPolicyAnswer)
            assert replay_a.question == live_a.question, f"answer {i}: question mismatch"
            assert replay_a.answer == live_a.answer, f"answer {i}: answer mismatch"

    finally:
        await client.aclose()


# Test 6: LiveShopify is a ShopifyMCPClient and satisfies ShopDataSource
@pytest.mark.asyncio
async def test_liveshopify_isinstance_client_and_has_interface():
    """Construct LiveShopify, assert isinstance(ShopifyMCPClient),
    and all six ShopDataSource methods are callable."""
    from bigbrain.shopify.client import ShopifyMCPClient

    live = LiveShopify(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
    )

    try:
        # Assert it's a ShopifyMCPClient
        assert isinstance(live, ShopifyMCPClient)

        # Assert all six ShopDataSource methods are present and callable
        assert callable(live.search_catalog)
        assert callable(live.lookup_catalog)
        assert callable(live.get_product)
        assert callable(live.search_policies)
        assert callable(live.create_cart)
        assert callable(live.update_cart)

    finally:
        await live.aclose()


# Test 7: Multiple recorded entries for different tools coexist correctly
@pytest.mark.asyncio
async def test_multiple_tools_same_cassette(
    tmp_path, search_catalog_fixture, search_policies_fixture
):
    """Record a search_catalog and a search_policies call to the same cassette.
    Replay both through one ReplayShopify instance and assert both return correct results."""
    from bigbrain.shopify.client import ShopifyMCPClient

    cassette_path = tmp_path / "test-shop.example.com" / "cassette.jsonl"
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        record_path=cassette_path,
    )

    try:
        # Prepare mocks for both endpoints
        catalog_structured = search_catalog_fixture["result"]["structuredContent"]
        catalog_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": catalog_structured,
        }

        policies_result = search_policies_fixture["result"]
        policies_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": policies_result,
        }

        with respx.mock:
            # Mock both endpoints
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=catalog_response)
            )
            respx.post("https://test-shop.example.com/api/mcp").mock(
                return_value=Response(200, json=policies_response)
            )

            # Record both calls
            live_products, _ = await client.search_catalog(query="wool runner shoes")
            live_answers = await client.search_policies("what is your return policy")

        # Replay both through one ReplayShopify instance
        replay = ReplayShopify(tmp_path, "test-shop.example.com")
        replay_products, _ = await replay.search_catalog(query="wool runner shoes")
        replay_answers = await replay.search_policies("what is your return policy")

        # Assert both results are correct and distinct
        assert len(replay_products) == len(live_products)
        assert len(replay_answers) == len(live_answers)
        assert all(isinstance(p, ShopProduct) for p in replay_products)
        assert all(isinstance(a, ShopPolicyAnswer) for a in replay_answers)

    finally:
        await client.aclose()


# Test 8: Cassette directory structure
@pytest.mark.asyncio
async def test_cassette_directory_structure(tmp_path, search_catalog_fixture):
    """After recording with record_path=tmp_path/<shop>/<cassette.jsonl>,
    assert the file exists at exactly that path (parent directories created as needed)."""
    from bigbrain.shopify.client import ShopifyMCPClient

    cassette_path = tmp_path / "some-shop.example.com" / "cassette.jsonl"
    client = ShopifyMCPClient(
        "some-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        record_path=cassette_path,
    )

    try:
        structured = search_catalog_fixture["result"]["structuredContent"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": structured,
        }

        with respx.mock:
            respx.post("https://some-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Make the call to populate the cassette
            await client.search_catalog(query="test")

        # Assert the cassette file exists at exactly the specified path
        assert cassette_path.exists()
        assert cassette_path.is_file()
        # Assert parent directory structure exists
        assert cassette_path.parent == tmp_path / "some-shop.example.com"
        assert cassette_path.parent.exists()

    finally:
        await client.aclose()
