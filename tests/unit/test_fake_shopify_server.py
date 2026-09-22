"""Tests for FakeShopifyMCPServer: a FastAPI app serving recorded fixtures over
the same JSON-RPC interface as real Shopify stores (M2 milestone).
All tests are fully offline using respx to mock HTTP calls and recorded cassettes.
"""

import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

from bigbrain.shopify.client import ShopifyMCPClient
from bigbrain.shopify.fake_server import create_fake_shopify_app
from bigbrain.shopify.models import ShopProduct


@pytest.fixture
def search_catalog_fixture():
    """Load real search_catalog response fixture."""
    with open("tests/unit/data/shopify_live_samples/search_catalog_response.json") as f:
        return json.load(f)


@pytest.fixture
def search_policies_fixture():
    """Load real search_policies response fixture."""
    with open("tests/unit/data/shopify_live_samples/search_policies_response.json") as f:
        return json.load(f)


# Test 1: tools/list on UCP endpoint returns hardcoded UCP tool names
def test_tools_list_ucp_endpoint(tmp_path):
    """POST to /api/ucp/mcp with method=tools/list returns the hardcoded UCP
    tool names (search_catalog, lookup_catalog, get_product)."""
    app = create_fake_shopify_app(tmp_path, "test-shop.example.com")
    client = TestClient(app)

    response = client.post(
        "/api/ucp/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
            "params": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert "result" in body
    assert "tools" in body["result"]

    tools = body["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert tool_names == ["search_catalog", "lookup_catalog", "get_product"]


# Test 2: tools/list on policy endpoint returns hardcoded policy tool name
def test_tools_list_policy_endpoint(tmp_path):
    """POST to /api/mcp with method=tools/list returns the hardcoded policy
    tool name (search_shop_policies_and_faqs)."""
    app = create_fake_shopify_app(tmp_path, "test-shop.example.com")
    client = TestClient(app)

    response = client.post(
        "/api/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
            "params": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert "result" in body
    assert "tools" in body["result"]

    tools = body["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert tool_names == ["search_shop_policies_and_faqs"]


# Test 3: tools/call for recorded search_catalog entry returns recorded result
# (with meta stripping on matching)
@pytest.mark.asyncio
async def test_tools_call_recorded_search_catalog(tmp_path, search_catalog_fixture):
    """Record a search_catalog call via real client, then call through the fake server
    with the same arguments (plus a 'meta' block). Assert the fake server strips 'meta'
    for matching and returns the recorded result."""
    cassette_path = tmp_path / "test-shop.example.com" / "cassette.jsonl"
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        record_path=cassette_path,
    )

    try:
        # Mock and record a search_catalog call
        structured = search_catalog_fixture["result"]["structuredContent"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [], "isError": False, "structuredContent": structured},
        }

        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Record the call
            await client.search_catalog(query="wool runner shoes")

        # Now test the fake server: construct it and make the same call
        fake_app = create_fake_shopify_app(tmp_path, "test-shop.example.com")
        test_client = TestClient(fake_app)

        # Call with the same arguments (including meta to test stripping)
        response = test_client.post(
            "/api/ucp/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": "search_catalog",
                    "arguments": {
                        "meta": {"ucp-agent": {"profile": "test"}},
                        "catalog": {
                            "query": "wool runner shoes",
                            "pagination": {"limit": 10},
                        },
                    },
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == 1
        assert "result" in body
        # The fake server returns the raw recorded result verbatim (structuredContent
        # envelope and all), matching real Shopify's wire shape (docs/SHOPIFY_NOTES.md).
        assert "structuredContent" in body["result"]
        assert "products" in body["result"]["structuredContent"]

        # Assert products match the recorded data
        products = body["result"]["structuredContent"]["products"]
        assert len(products) > 0
        first_product = products[0]
        assert "id" in first_product
        assert "description" in first_product

    finally:
        await client.aclose()


# Test 4: tools/call for unrecorded entry returns 404 with error
def test_tools_call_unrecorded_returns_404(tmp_path):
    """Call tools/call with arguments that were never recorded. Should return
    404 with a JSON-RPC error body (not 200 with empty result)."""
    app = create_fake_shopify_app(tmp_path, "test-shop.example.com")
    client = TestClient(app)

    response = client.post(
        "/api/ucp/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 1,
            "params": {
                "name": "search_catalog",
                "arguments": {
                    "catalog": {
                        "query": "something that was never recorded",
                        "pagination": {"limit": 10},
                    },
                },
            },
        },
    )

    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "message" in body["error"]
    assert "code" in body["error"]
    # Confirm it's not a 200 success response
    assert "result" not in body or body.get("result") is None


# Test 5: End-to-end with real ShopifyMCPClient routed through ASGITransport
@pytest.mark.asyncio
async def test_end_to_end_asgi_transport(tmp_path, search_catalog_fixture):
    """Record a search_catalog call, construct fake app, route a real
    ShopifyMCPClient through httpx.ASGITransport (no real network), and
    call search_catalog on it. Assert it returns real ShopProduct instances
    with expected data -- proving protocol compatibility end to end."""
    cassette_path = tmp_path / "test-shop.example.com" / "cassette.jsonl"
    client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        rate_per_sec=1000,
        backoff_base_s=0.01,
        record_path=cassette_path,
    )

    try:
        # Mock and record a search_catalog call
        structured = search_catalog_fixture["result"]["structuredContent"]
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [], "isError": False, "structuredContent": structured},
        }

        with respx.mock:
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            # Record the call
            await client.search_catalog(query="wool runner shoes")

    finally:
        await client.aclose()

    # Construct fake app and ASGITransport-backed HTTP client
    fake_app = create_fake_shopify_app(tmp_path, "test-shop.example.com")
    transport = httpx.ASGITransport(app=fake_app)
    http_client = httpx.AsyncClient(transport=transport, base_url="https://test-shop.example.com")

    # Create real client routed through the transport
    real_client = ShopifyMCPClient(
        "test-shop.example.com",
        "https://example.com/profile.json",
        http_client=http_client,
    )

    try:
        # Call search_catalog through the client (which routes through ASGITransport)
        products, pagination = await real_client.search_catalog(query="wool runner shoes")

        # Assert we got real ShopProduct instances
        assert isinstance(products, list)
        assert len(products) > 0
        assert all(isinstance(p, ShopProduct) for p in products)

        # Assert specific product data matches what was recorded
        first_product = products[0]
        assert first_product.id is not None
        assert first_product.description is not None
        assert first_product.description.html is not None
        assert isinstance(first_product.description.html, str)
        assert len(first_product.description.html) > 0

        # Assert pagination data is present
        assert isinstance(pagination, dict)

    finally:
        await real_client.aclose()


# Test 6: Unknown JSON-RPC method returns 400 with error
def test_unknown_method_returns_400(tmp_path):
    """POST with an unknown method name should return 400 with a JSON-RPC error body."""
    app = create_fake_shopify_app(tmp_path, "test-shop.example.com")
    client = TestClient(app)

    response = client.post(
        "/api/ucp/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "not_a_real_method",
            "id": 1,
            "params": {},
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert "error" in body
    assert "message" in body["error"]
    assert "code" in body["error"]
    # Confirm it's not a success response
    assert "result" not in body or body.get("result") is None
