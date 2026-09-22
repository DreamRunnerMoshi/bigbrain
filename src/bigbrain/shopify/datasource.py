"""ShopDataSource: the interface BigBrainShop workers read a Shopify store through
(spec section 5.1.4). Two implementations here: `LiveShopify` (a `ShopifyMCPClient`
subclass -- talks to the real store) and `ReplayShopify` (serves a recorded JSONL
cassette, offline, deterministic). A future `SyntheticShop` (sim mode, a later
milestone) will implement the same interface over a synthetic market instead of real
Shopify data. Agents only ever depend on `ShopDataSource`, never on `ShopifyMCPClient`
directly, so sim/replay/live/net modes (spec section 3) share the same downstream code.

`ReplayShopify` reads the exact cassette format `ShopifyMCPClient._record()` writes
(shopify/client.py): one JSONL line per call, `{"tool": ..., "arguments": <"meta" key
stripped>, "result": ..., "recorded_at": ...}` at `fixtures/shopify/<shop>/cassette.jsonl`
(spec section 5.1.5). Lookup is an exact match on (tool, canonical JSON of arguments) --
if a call wasn't in the recorded cassette, this raises rather than silently returning
something else, so a replay run is a faithful, deterministic stand-in for whatever was
actually recorded (spec section 0: "every experiment run is reproducible ... from their
recorded cassettes").
"""

from pathlib import Path
from typing import Any, Protocol

from bigbrain.common.canonical import canonical_json_bytes
from bigbrain.shopify.client import ShopifyMCPClient
from bigbrain.shopify.models import ShopCart, ShopPolicyAnswer, ShopProduct


class ShopDataSource(Protocol):
    """Structural interface -- `LiveShopify`, `ReplayShopify`, and (later)
    `SyntheticShop` all satisfy this without inheriting from it."""

    async def search_catalog(
        self,
        query: str | None = None,
        *,
        filters: dict | None = None,
        context: dict | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> tuple[list[ShopProduct], dict]: ...

    async def lookup_catalog(self, ids: list[str]) -> list[ShopProduct]: ...

    async def get_product(
        self, product_id: str, *, selected: list[dict] | None = None
    ) -> ShopProduct: ...

    async def search_policies(self, query: str) -> list[ShopPolicyAnswer]: ...

    async def create_cart(self, line_items: list[dict]) -> ShopCart: ...

    async def update_cart(self, cart_id: str, line_items: list[dict]) -> ShopCart: ...


class LiveShopify(ShopifyMCPClient):
    """`ShopDataSource` backed by a real `ShopifyMCPClient` -- live mode (spec section
    3). No behavior beyond `ShopifyMCPClient`; this subclass exists only so
    construction code reads `LiveShopify(...)`, matching spec section 5.1.4's naming,
    while `ShopDataSource`-typed code elsewhere doesn't care which concrete class it
    received.
    """


class FixtureNotFoundError(Exception):
    """No recorded cassette entry matches this (tool, arguments) pair. Raised rather
    than silently falling back to something else -- see module docstring."""

    def __init__(self, shop_domain: str, tool: str) -> None:
        self.shop_domain = shop_domain
        self.tool = tool
        super().__init__(
            f"no recorded {tool} call for {shop_domain} matching these arguments "
            f"(cassette incomplete for this replay run)"
        )


class ReplayShopify:
    """`ShopDataSource` backed by a recorded JSONL cassette (spec section 5.1.4/5.1.5).
    Offline, deterministic. Loads `<fixtures_dir>/<shop_domain>/cassette.jsonl` (if it
    exists -- a missing file just means an empty cassette, every lookup will raise
    `FixtureNotFoundError`) into an in-memory index keyed by (tool, canonical JSON of
    the arguments actually sent, "meta" excluded).
    """

    def __init__(self, fixtures_dir: Path, shop_domain: str) -> None:
        import json

        self.shop_domain = shop_domain
        self.cassette_path = Path(fixtures_dir) / shop_domain / "cassette.jsonl"
        self._index: dict[tuple[str, bytes], dict] = {}
        if self.cassette_path.exists():
            with self.cassette_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    key = (entry["tool"], canonical_json_bytes(entry["arguments"]))
                    self._index[key] = entry["result"]

    def get_raw_result(self, tool: str, arguments: dict[str, Any]) -> dict:
        """Public raw lookup: the recorded `result` dict for (tool, arguments), with
        no `ShopProduct`/etc. parsing applied. Used by `FakeShopifyMCPServer`, which
        needs to answer a live JSON-RPC request with whatever was actually recorded,
        not a typed model.
        """
        return self._lookup(tool, arguments)

    def _lookup(self, tool: str, arguments: dict[str, Any]) -> dict:
        key = (tool, canonical_json_bytes(arguments))
        if key not in self._index:
            raise FixtureNotFoundError(self.shop_domain, tool)
        return self._index[key]

    @staticmethod
    def _unwrap(result: dict) -> dict:
        """Same unwrapping as ShopifyMCPClient._unwrap() (shopify/client.py) --
        catalog/cart tool results nest the actual data inside
        `result.structuredContent` (docs/SHOPIFY_NOTES.md). Falls back to `result`
        itself if absent.
        """
        return result.get("structuredContent", result)

    async def search_catalog(
        self,
        query: str | None = None,
        *,
        filters: dict | None = None,
        context: dict | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> tuple[list[ShopProduct], dict]:
        catalog: dict[str, Any] = {}
        if query is not None:
            catalog["query"] = query
        if filters is not None:
            catalog["filters"] = filters
        if context is not None:
            catalog["context"] = context
        pagination: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            pagination["cursor"] = cursor
        catalog["pagination"] = pagination

        result = self._lookup("search_catalog", {"catalog": catalog})
        data = self._unwrap(result)
        products = [ShopProduct.model_validate(p) for p in data.get("products", [])]
        return products, data.get("pagination", {})

    async def lookup_catalog(self, ids: list[str]) -> list[ShopProduct]:
        result = self._lookup("lookup_catalog", {"catalog": {"ids": ids}})
        data = self._unwrap(result)
        return [ShopProduct.model_validate(p) for p in data.get("products", [])]

    async def get_product(
        self, product_id: str, *, selected: list[dict] | None = None
    ) -> ShopProduct:
        catalog: dict[str, Any] = {"id": product_id}
        if selected is not None:
            catalog["selected"] = selected
        result = self._lookup("get_product", {"catalog": catalog})
        data = self._unwrap(result)
        return ShopProduct.model_validate(data["product"])

    async def search_policies(self, query: str) -> list[ShopPolicyAnswer]:
        import json as _json

        result = self._lookup("search_shop_policies_and_faqs", {"query": query})
        text = result["content"][0]["text"]
        answers_raw = _json.loads(text)
        return [ShopPolicyAnswer.model_validate(a) for a in answers_raw]

    async def create_cart(self, line_items: list[dict]) -> ShopCart:
        result = self._lookup("create_cart", {"cart": {"line_items": line_items}})
        data = self._unwrap(result)
        return ShopCart.model_validate(data.get("cart", data))

    async def update_cart(self, cart_id: str, line_items: list[dict]) -> ShopCart:
        result = self._lookup("update_cart", {"cart": {"id": cart_id, "line_items": line_items}})
        data = self._unwrap(result)
        return ShopCart.model_validate(data.get("cart", data))
