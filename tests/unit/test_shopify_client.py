"""Tests for ShopifyMCPClient (M2 milestone). All tests are fully offline using respx
to mock HTTP calls; no real network access or API keys required.
"""

import json

import pytest
import respx
from httpx import Response

from bigbrain.shopify.client import (
    ShopifyAPIError,
    ShopifyCircuitOpenError,
    ShopifyForbiddenError,
    ShopifyMCPClient,
)
from bigbrain.shopify.models import ShopCart, ShopPolicyAnswer, ShopProduct


# Fixtures for fast test execution (high rate limits, fast backoff, quick retries)
@pytest.fixture
def fast_client():
    """Fast-executing client for unit tests (no real delays)."""
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        max_retries=2,
    )
    yield client
    # Clean up: close the HTTP client if it was owned by this client
    # (no need to await since pytest-asyncio handles this)


@pytest.fixture
def fast_client_with_cleanup():
    """Fast-executing client for async tests with cleanup."""
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        max_retries=2,
    )
    return client


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


@pytest.fixture
def ucp_tools_list_fixture():
    """Load real ucp_tools_list response fixture."""
    with open("tests/unit/data/shopify_live_samples/ucp_tools_list_response.json") as f:
        return json.load(f)


# Test 1: search_catalog success
@pytest.mark.asyncio
async def test_search_catalog_success(fast_client_with_cleanup, search_catalog_fixture):
    """Mock a 200 response using real search_catalog data. Call client.search_catalog
    with a query, assert it returns ShopProduct list with populated description.html
    and pagination matches the mock data.
    """
    client = fast_client_with_cleanup
    try:
        with respx.mock:
            # Extract structured content from the real fixture
            # (fixture has both content and structuredContent, we use structuredContent)
            structured = search_catalog_fixture["result"]["structuredContent"]
            mock_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": structured,
            }

            # Mock UCP endpoint for search_catalog
            ucp_route = respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Call search_catalog
            products, pagination = await client.search_catalog(query="wool runner shoes")

            # Assert it returns ShopProduct instances (not raw dicts)
            assert isinstance(products, list)
            assert len(products) > 0
            assert all(isinstance(p, ShopProduct) for p in products)

            # Assert first product's description.html is populated
            first_product = products[0]
            assert first_product.description is not None
            assert first_product.description.html is not None
            assert len(first_product.description.html) > 0

            # Assert pagination matches mock data
            expected_pagination = structured["pagination"]
            assert pagination == expected_pagination

            # Verify the call was made
            assert ucp_route.called
    finally:
        await client.aclose()


# Test 2: get_product success
@pytest.mark.asyncio
async def test_get_product_success(fast_client_with_cleanup, get_product_fixture):
    """Mock using real get_product data. Call client.get_product with a real id,
    assert it returns a single ShopProduct with the right .id.
    """
    client = fast_client_with_cleanup
    try:
        # Extract real product id from fixture (in structuredContent)
        real_product_id = get_product_fixture["result"]["structuredContent"]["product"]["id"]

        # Extract structured content from the real fixture
        structured = get_product_fixture["result"]["structuredContent"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": structured,
        }

        with respx.mock:
            ucp_route = respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Call get_product
            product = await client.get_product(real_product_id)

            # Assert it returns a ShopProduct
            assert isinstance(product, ShopProduct)

            # Assert the id matches
            assert product.id == real_product_id

            # Verify the call was made
            assert ucp_route.called
    finally:
        await client.aclose()


# Test 3: search_policies success, no structuredContent
@pytest.mark.asyncio
async def test_search_policies_success(fast_client_with_cleanup, search_policies_fixture):
    """Mock using real policies response shape (content[0].text as JSON string,
    no structuredContent key). Call client.search_policies, assert it returns
    ShopPolicyAnswer list with at least 2 entries and non-empty question/answer.
    """
    client = fast_client_with_cleanup
    try:
        with respx.mock:
            # Use the result from fixture directly (it has content, no structuredContent)
            result = search_policies_fixture["result"]
            mock_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": result,
            }

            policy_route = respx.post("https://test-shop.example.com/api/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Call search_policies
            answers = await client.search_policies("what is your return policy")

            # Assert it returns ShopPolicyAnswer instances
            assert isinstance(answers, list)
            assert len(answers) >= 2

            # Assert all entries have non-empty question and answer
            for answer in answers:
                assert isinstance(answer, ShopPolicyAnswer)
                assert answer.question and len(answer.question) > 0
                assert answer.answer and len(answer.answer) > 0

            # Verify the mock genuinely has no structuredContent key
            assert "structuredContent" not in result

            # Verify the call was made
            assert policy_route.called
    finally:
        await client.aclose()


# Test 4: 403 raises ShopifyForbiddenError and force-opens circuit
@pytest.mark.asyncio
async def test_403_forbidden_and_circuit_open(fast_client_with_cleanup):
    """Mock a 403 response. Call search_catalog, assert ShopifyForbiddenError is
    raised and client.circuit_breaker.is_open is True afterward.
    """
    client = fast_client_with_cleanup
    try:
        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(return_value=Response(403))

            # Call should raise ShopifyForbiddenError
            with pytest.raises(ShopifyForbiddenError):
                await client.search_catalog(query="test")

            # Assert circuit is open
            assert client.circuit_breaker.is_open is True
    finally:
        await client.aclose()


# Test 5: 429 retries then succeeds
@pytest.mark.asyncio
async def test_429_retry_success(fast_client_with_cleanup, search_catalog_fixture):
    """Mock respx to return 429 on first call and 200 success on second.
    Call search_catalog, assert it succeeds and the route was called exactly 2 times.
    """
    client = fast_client_with_cleanup
    try:
        # Extract structured content for the success response
        structured = search_catalog_fixture["result"]["structuredContent"]
        success_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": structured,
        }

        with respx.mock:
            # Use side_effect to return different responses on successive calls
            route = respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                side_effect=[
                    Response(429),
                    Response(200, json=success_response),
                ]
            )

            # Call search_catalog
            products, pagination = await client.search_catalog(query="shoes")

            # Assert it succeeds
            assert isinstance(products, list)
            assert len(products) > 0

            # Assert the route was called exactly 2 times
            assert len(route.calls) == 2
    finally:
        await client.aclose()


# Test 6: 429 exhausts retries, circuit records exactly one failure
@pytest.mark.asyncio
async def test_429_exhausts_retries_one_failure(fast_client_with_cleanup):
    """Mock respx to always return 429. Construct client with max_retries=2.
    Call search_catalog, assert ShopifyAPIError is raised and
    client.circuit_breaker._consecutive_failures == 1 (NOT 3).
    """
    # Create client with max_retries=2 explicitly
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        max_retries=2,
    )
    try:
        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(return_value=Response(429))

            # Call should raise ShopifyAPIError
            with pytest.raises(ShopifyAPIError):
                await client.search_catalog(query="test")

            # Assert circuit breaker recorded exactly one failure
            # (not one per retry attempt, but one for the whole call)
            assert client.circuit_breaker._consecutive_failures == 1
    finally:
        await client.aclose()


# Test 7: 5xx follows same retry path as 429
@pytest.mark.asyncio
async def test_500_retry_behavior(fast_client_with_cleanup):
    """Mock a 500 response (always), assert same retry-then-raise behavior as 429."""
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        max_retries=2,
    )
    try:
        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(return_value=Response(500))

            # Call should raise ShopifyAPIError
            with pytest.raises(ShopifyAPIError):
                await client.search_catalog(query="test")

            # Assert circuit breaker recorded exactly one failure
            assert client.circuit_breaker._consecutive_failures == 1
    finally:
        await client.aclose()


# Test 8: Circuit open short-circuits before HTTP call
@pytest.mark.asyncio
async def test_circuit_open_no_call(fast_client_with_cleanup):
    """Manually call client.circuit_breaker.force_open() before search_catalog.
    Assert ShopifyCircuitOpenError is raised AND the respx route was never called.
    """
    client = fast_client_with_cleanup
    try:
        with respx.mock:
            route = respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json={"result": {"products": []}})
            )

            # Force circuit open
            client.circuit_breaker.force_open()

            # Call should raise ShopifyCircuitOpenError
            with pytest.raises(ShopifyCircuitOpenError):
                await client.search_catalog(query="test")

            # Assert route was never called (0 calls)
            assert len(route.calls) == 0
    finally:
        await client.aclose()


# Test 9: Caching - repeated identical calls hit mock once
@pytest.mark.asyncio
async def test_caching_repeated_calls(fast_client_with_cleanup, search_catalog_fixture):
    """Mock success response, call search_catalog twice with identical arguments.
    Assert the route was called exactly 1 time and both results are equal.
    """
    client = fast_client_with_cleanup
    try:
        # Extract structured content for the success response
        structured = search_catalog_fixture["result"]["structuredContent"]
        success_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": structured,
        }

        with respx.mock:
            route = respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=success_response)
            )

            # Call with identical arguments twice
            result1 = await client.search_catalog(query="shoes")
            result2 = await client.search_catalog(query="shoes")

            # Assert both results are equal
            assert result1[0] == result2[0]  # products
            assert result1[1] == result2[1]  # pagination

            # Assert the route was called exactly 1 time (second call from cache)
            assert len(route.calls) == 1
    finally:
        await client.aclose()


# Test 10: Mutating calls not cached
@pytest.mark.asyncio
async def test_mutating_calls_not_cached(fast_client_with_cleanup):
    """Mock create_cart endpoint to return valid cart response TWICE.
    Call create_cart twice with identical arguments, assert route was called 2 times.
    """
    client = fast_client_with_cleanup
    try:
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"cart": {"id": "gid://shopify/Cart/1"}},
        }

        with respx.mock:
            route = respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Call create_cart twice with identical arguments
            line_items = [{"item": {"id": "variant-1"}, "quantity": 1}]
            cart1 = await client.create_cart(line_items)
            cart2 = await client.create_cart(line_items)

            # Assert both are ShopCart instances
            assert isinstance(cart1, ShopCart)
            assert isinstance(cart2, ShopCart)

            # Assert route was called 2 times (not cached)
            assert len(route.calls) == 2
    finally:
        await client.aclose()


# Test 11: JSON-RPC error in 200 response
@pytest.mark.asyncio
async def test_json_rpc_error_200(fast_client_with_cleanup):
    """Mock a 200 response with JSON-RPC error (the real error from SHOPIFY_NOTES.md).
    Call search_catalog, assert ShopifyAPIError is raised with correct code and message.
    """
    client = fast_client_with_cleanup
    try:
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32001,
                "message": "UCP discovery failed",
                "data": {"code": "invalid_profile_url"},
            },
        }

        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=error_response)
            )

            # Call should raise ShopifyAPIError
            with pytest.raises(ShopifyAPIError) as exc_info:
                await client.search_catalog(query="test")

            # Assert error has correct code and message
            assert exc_info.value.code == -32001
            assert exc_info.value.message == "UCP discovery failed"
    finally:
        await client.aclose()


# Test 12: Agent profile is actually sent in request
@pytest.mark.asyncio
async def test_agent_profile_in_request(fast_client_with_cleanup, search_catalog_fixture):
    """Construct client with distinctive agent_profile_url, mock success response.
    Make search_catalog call, inspect request body and assert
    body["params"]["arguments"]["meta"]["ucp-agent"]["profile"] matches.
    """
    # Create client with distinctive profile URL
    distinctive_profile = "https://example.com/my-profile.json"
    client = ShopifyMCPClient(
        "test-shop.example.com",
        distinctive_profile,
        rate_per_sec=1000,
        backoff_base_s=0.01,
        max_retries=2,
    )
    try:
        # Extract structured content for the success response
        structured = search_catalog_fixture["result"]["structuredContent"]
        success_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": structured,
        }

        with respx.mock:
            route = respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=success_response)
            )

            # Make search_catalog call
            await client.search_catalog(query="test")

            # Inspect the request body that was captured
            assert len(route.calls) > 0
            request = route.calls.last.request
            request_body = json.loads(request.content)

            # Assert the profile URL was sent correctly
            profile_in_request = request_body["params"]["arguments"]["meta"]["ucp-agent"]["profile"]
            assert profile_in_request == distinctive_profile
    finally:
        await client.aclose()


# Test 13: list_tools success
@pytest.mark.asyncio
async def test_list_tools_success(fast_client_with_cleanup, ucp_tools_list_fixture):
    """Mock using real ucp_tools_list response. Call client.list_tools(),
    assert it returns list of tool dicts and search_catalog is among them.
    """
    client = fast_client_with_cleanup
    try:
        # Use the fixture result directly
        result = ucp_tools_list_fixture["result"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": result,
        }

        with respx.mock:
            route = respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Call list_tools
            tools = await client.list_tools()

            # Assert it returns a list of dicts
            assert isinstance(tools, list)
            assert all(isinstance(t, dict) for t in tools)

            # Assert search_catalog is among the tool names
            tool_names = [t["name"] for t in tools]
            assert "search_catalog" in tool_names

            # Verify the call was made
            assert route.called
    finally:
        await client.aclose()


# Test 14: aclose() doesn't error
@pytest.mark.asyncio
async def test_aclose_no_error():
    """Construct client without http_client parameter (owns its own AsyncClient).
    Call aclose(), assert it doesn't error.
    """
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        max_retries=2,
    )

    # Call aclose - should not raise
    await client.aclose()


@pytest.mark.asyncio
async def test_record_path_writes_cassette_without_meta(tmp_path, search_catalog_fixture):
    """A client constructed with record_path writes one JSONL cassette line per
    successful call, with `meta` stripped from the recorded arguments (it's a
    record-time credential, not part of what identifies the call for replay).
    """
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
        success_response = {"jsonrpc": "2.0", "id": 1, "result": structured}
        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=success_response)
            )
            await client.search_catalog(query="wool runner shoes")

        assert cassette_path.exists()
        lines = cassette_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["tool"] == "search_catalog"
        assert "meta" not in entry["arguments"]
        assert entry["arguments"]["catalog"]["query"] == "wool runner shoes"
        assert entry["result"] == structured
        assert "recorded_at" in entry
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_no_record_path_writes_nothing(tmp_path, search_catalog_fixture):
    """Without record_path (the default), no cassette file is created."""
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
    )
    try:
        structured = search_catalog_fixture["result"]["structuredContent"]
        success_response = {"jsonrpc": "2.0", "id": 1, "result": structured}
        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=success_response)
            )
            await client.search_catalog(query="wool runner shoes")

        assert list(tmp_path.iterdir()) == []
    finally:
        await client.aclose()
