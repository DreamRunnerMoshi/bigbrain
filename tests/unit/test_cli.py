"""Tests for the Typer CLI (bigbrain/ui/cli.py). All tests are fully offline using respx
to mock HTTP calls; no real network access or API keys required. Uses typer.testing.CliRunner
for command invocation.
"""

import json
import tempfile
from pathlib import Path

import pytest
import respx
import yaml
from httpx import Response
from typer.testing import CliRunner

from bigbrain.ui.cli import app

runner = CliRunner()


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


# Test 1: probe success on both endpoints
def test_probe_success_both_endpoints(ucp_tools_list_fixture):
    """Mock 200 responses for tools/list on both UCP and policy endpoints.
    Assert exit code 0 and output mentions search_catalog (from UCP) and
    search_shop_policies_and_faqs (from policy endpoint).
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"shopify_agent_profile_url": "https://example.com/profile.json"}
        yaml.dump(config, f)
        config_path = f.name

    try:
        with respx.mock:
            # UCP tools/list response (uses the fixture)
            ucp_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": ucp_tools_list_fixture["result"],
            }
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=ucp_response)
            )

            # Policy endpoint tools/list response (minimal)
            policy_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"tools": [{"name": "search_shop_policies_and_faqs"}]},
            }
            respx.post("https://test-shop.example.com/api/mcp").mock(
                return_value=Response(200, json=policy_response)
            )

            result = runner.invoke(
                app, ["shopify", "probe", "test-shop.example.com", "--config", config_path]
            )

            assert result.exit_code == 0
            assert "search_catalog" in result.stdout
            assert "search_shop_policies_and_faqs" in result.stdout
    finally:
        Path(config_path).unlink()


# Test 2: probe reports a restricted endpoint without crashing
def test_probe_restricted_endpoint():
    """Mock UCP endpoint to return 403, policy endpoint succeeds.
    Assert exit code 0 and output mentions 'RESTRICTED' for UCP.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {"shopify_agent_profile_url": "https://example.com/profile.json"}
        yaml.dump(config, f)
        config_path = f.name

    try:
        with respx.mock:
            # UCP returns 403 with JSON-RPC error response
            ucp_error_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32001, "message": "Forbidden"},
            }
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(403, json=ucp_error_response)
            )

            # Policy succeeds
            policy_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"tools": [{"name": "search_shop_policies_and_faqs"}]},
            }
            respx.post("https://test-shop.example.com/api/mcp").mock(
                return_value=Response(200, json=policy_response)
            )

            result = runner.invoke(
                app, ["shopify", "probe", "test-shop.example.com", "--config", config_path]
            )

            assert result.exit_code == 0
            assert "RESTRICTED" in result.stdout
    finally:
        Path(config_path).unlink()


# Test 3: probe with no config and no profile URL still runs
def test_probe_no_profile_url():
    """Invoke probe with no --config (uses default empty-string profile).
    Mock both endpoints return 422 JSON-RPC error.
    Assert exit code 0 and output contains warning about missing profile URL.
    """
    with respx.mock:
        # Both endpoints return 422 error
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32001, "message": "UCP discovery failed"},
        }
        respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
            return_value=Response(422, json=error_response)
        )
        respx.post("https://test-shop.example.com/api/mcp").mock(
            return_value=Response(422, json=error_response)
        )

        result = runner.invoke(app, ["shopify", "probe", "test-shop.example.com"])

        assert result.exit_code == 0
        assert "Warning" in result.stdout
        assert "shopify_agent_profile_url" in result.stdout
        assert "RESTRICTED" in result.stdout


# Test 4: record writes a cassette from a YAML script with one entry
def test_record_single_search_catalog(search_catalog_fixture):
    """Create a temp script YAML with one search_catalog entry.
    Mock successful response, temp config, temp fixtures-dir.
    Assert exit code 0 and cassette file created with exactly one line.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create script
        script_data = {"search_catalog": ["wool runner"]}
        script_path = Path(tmpdir) / "script.yaml"
        script_path.write_text(yaml.dump(script_data))

        # Create config
        config_data = {"shopify_agent_profile_url": "https://example.com/profile.json"}
        config_path = Path(tmpdir) / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        # Fixtures dir
        fixtures_dir = Path(tmpdir) / "fixtures"

        with respx.mock:
            # Mock search_catalog
            result_data = search_catalog_fixture["result"]["structuredContent"]
            mock_response = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": result_data,
            }
            respx.post("https://test-shop.example.com/api/ucp/mcp").mock(
                return_value=Response(200, json=mock_response)
            )

            result = runner.invoke(
                app,
                [
                    "shopify",
                    "record",
                    "--shop",
                    "test-shop.example.com",
                    "--script",
                    str(script_path),
                    "--fixtures-dir",
                    str(fixtures_dir),
                    "--config",
                    str(config_path),
                ],
            )

            assert result.exit_code == 0
            assert "Recorded to" in result.stdout

            # Check cassette file
            cassette_path = fixtures_dir / "test-shop.example.com" / "cassette.jsonl"
            assert cassette_path.exists()

            # Verify exactly one line
            lines = cassette_path.read_text().strip().split("\n")
            assert len(lines) == 1

            # Verify tool field
            entry = json.loads(lines[0])
            assert entry["tool"] == "search_catalog"


# Test 5: record with all three script keys populated
def test_record_all_three_tools(
    search_catalog_fixture, get_product_fixture, search_policies_fixture
):
    """Create a script with one entry each for search_catalog, get_product, search_policies.
    Mock all three tool responses (using real fixtures).
    Assert cassette has exactly 3 lines, one per tool.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create script with all three tools
        script_data = {
            "search_catalog": ["shoes"],
            "get_product": ["gid://shopify/Product/123"],
            "search_policies": ["what is your return policy"],
        }
        script_path = Path(tmpdir) / "script.yaml"
        script_path.write_text(yaml.dump(script_data))

        # Create config
        config_data = {"shopify_agent_profile_url": "https://example.com/profile.json"}
        config_path = Path(tmpdir) / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        # Fixtures dir
        fixtures_dir = Path(tmpdir) / "fixtures"

        with respx.mock:
            # Mock UCP endpoint for search_catalog and get_product
            search_result = search_catalog_fixture["result"]["structuredContent"]
            get_product_result = get_product_fixture["result"]["structuredContent"]

            # UCP endpoint returns different responses; respx will match sequentially
            ucp_route = respx.post("https://test-shop.example.com/api/ucp/mcp")
            ucp_route.side_effect = [
                Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": search_result,
                    },
                ),
                Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": get_product_result,
                    },
                ),
            ]

            # Mock search_policies (uses policy endpoint)
            policies_result = search_policies_fixture["result"]
            respx.post("https://test-shop.example.com/api/mcp").mock(
                return_value=Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": policies_result,
                    },
                )
            )

            result = runner.invoke(
                app,
                [
                    "shopify",
                    "record",
                    "--shop",
                    "test-shop.example.com",
                    "--script",
                    str(script_path),
                    "--fixtures-dir",
                    str(fixtures_dir),
                    "--config",
                    str(config_path),
                ],
            )

            assert result.exit_code == 0

            # Check cassette file
            cassette_path = fixtures_dir / "test-shop.example.com" / "cassette.jsonl"
            assert cassette_path.exists()

            # Verify exactly 3 lines
            lines = cassette_path.read_text().strip().split("\n")
            assert len(lines) == 3

            # Verify tool names (order doesn't matter, check as a set)
            tools = {json.loads(line)["tool"] for line in lines}
            assert tools == {"search_catalog", "get_product", "search_shop_policies_and_faqs"}


# Test 6: record continues past a single failed call
def test_record_continues_on_failure(search_catalog_fixture):
    """Script with two search_catalog entries: first fails (403), second succeeds.
    Assert command exits 0 and cassette contains exactly 1 successful entry.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create script with two search_catalog entries
        script_data = {
            "search_catalog": ["failed_query", "success_query"],
        }
        script_path = Path(tmpdir) / "script.yaml"
        script_path.write_text(yaml.dump(script_data))

        # Create config
        config_data = {"shopify_agent_profile_url": "https://example.com/profile.json"}
        config_path = Path(tmpdir) / "config.yaml"
        config_path.write_text(yaml.dump(config_data))

        # Fixtures dir
        fixtures_dir = Path(tmpdir) / "fixtures"

        with respx.mock:
            # First call fails with 403, second call succeeds
            search_result = search_catalog_fixture["result"]

            ucp_route = respx.post("https://test-shop.example.com/api/ucp/mcp")
            ucp_route.side_effect = [
                # First call fails with JSON-RPC error
                Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "error": {"code": -32001, "message": "Forbidden"},
                    },
                ),
                # Second call succeeds
                Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": search_result,
                    },
                ),
            ]

            result = runner.invoke(
                app,
                [
                    "shopify",
                    "record",
                    "--shop",
                    "test-shop.example.com",
                    "--script",
                    str(script_path),
                    "--fixtures-dir",
                    str(fixtures_dir),
                    "--config",
                    str(config_path),
                ],
            )

            # Command should exit with 0 (continues past failure)
            assert result.exit_code == 0

            # Check cassette file exists
            cassette_path = fixtures_dir / "test-shop.example.com" / "cassette.jsonl"
            assert cassette_path.exists()

            # Verify exactly 1 successful entry
            lines = cassette_path.read_text().strip().split("\n")
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["tool"] == "search_catalog"

            # Verify output mentions the failed query
            assert "failed" in result.stdout.lower()


# Test 7: bigbrain --help and bigbrain shopify --help work
def test_help_commands():
    """Verify that --help works for both main app and shopify subcommand."""
    # Test main app help
    result_main = runner.invoke(app, ["--help"])
    assert result_main.exit_code == 0
    assert len(result_main.stdout) > 0
    assert "BigBrain" in result_main.stdout or "shopify" in result_main.stdout

    # Test shopify subcommand help
    result_shopify = runner.invoke(app, ["shopify", "--help"])
    assert result_shopify.exit_code == 0
    assert len(result_shopify.stdout) > 0
    assert "shopify" in result_shopify.stdout or "Shopify" in result_shopify.stdout
