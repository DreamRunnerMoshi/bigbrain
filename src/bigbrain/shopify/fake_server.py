"""FakeShopifyMCPServer: a FastAPI app that serves recorded fixtures over the same
JSON-RPC interface real Shopify stores expose (BIGBRAIN_SPEC.md section 5.1.5) -- for
net-mode demos and CI to run fully offline. Reuses ReplayShopify's cassette lookup so
there is exactly one fixture format and one lookup implementation, not two.

`tools/list` is NOT served from the cassette (ShopifyMCPClient.list_tools() doesn't go
through the recording path -- see client.py's _call() vs list_tools()) -- it returns a
small hardcoded list of the tool names this project's client actually calls. This is a
deliberate simplification: tools/list is a diagnostic operation, not something whose
exact recorded shape matters for offline experiment reproducibility.
"""

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from bigbrain.shopify.datasource import FixtureNotFoundError, ReplayShopify

_UCP_TOOL_NAMES = ["search_catalog", "lookup_catalog", "get_product"]
_POLICY_TOOL_NAMES = ["search_shop_policies_and_faqs"]


def create_fake_shopify_app(fixtures_dir: Path, shop_domain: str) -> FastAPI:
    """One fake server instance serves one shop's recorded fixtures, at the same
    /api/ucp/mcp and /api/mcp paths the real store would use (docs/SHOPIFY_NOTES.md).
    """
    app = FastAPI(title=f"FakeShopifyMCPServer ({shop_domain})")
    replay = ReplayShopify(fixtures_dir, shop_domain)

    async def _handle(request: Request, tool_names: list[str]) -> JSONResponse:
        body = await request.json()
        method = body.get("method")
        rpc_id = body.get("id")

        if method == "tools/list":
            tools = [{"name": name, "description": "", "inputSchema": {}} for name in tool_names]
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": tools}})

        if method == "tools/call":
            params: dict[str, Any] = body.get("params", {})
            tool = params.get("name")
            arguments = params.get("arguments", {})
            match_arguments = {k: v for k, v in arguments.items() if k != "meta"}
            try:
                result = replay.get_raw_result(tool, match_arguments)
            except FixtureNotFoundError as exc:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": rpc_id,
                        "error": {"code": -32000, "message": str(exc)},
                    },
                    status_code=404,
                )
            return JSONResponse({"jsonrpc": "2.0", "id": rpc_id, "result": result})

        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"unknown method {method}"},
            },
            status_code=400,
        )

    @app.post("/api/ucp/mcp")
    async def ucp_endpoint(request: Request) -> JSONResponse:
        return await _handle(request, _UCP_TOOL_NAMES)

    @app.post("/api/mcp")
    async def policy_endpoint(request: Request) -> JSONResponse:
        return await _handle(request, _POLICY_TOOL_NAMES)

    return app
