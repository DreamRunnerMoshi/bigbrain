"""Shopify MCP client (BIGBRAIN_SPEC.md section 5.1.3). One instance talks to one
store's two endpoints (docs/SHOPIFY_NOTES.md): catalog/cart/checkout/order tools live
at POST https://{shop}/api/ucp/mcp, search_shop_policies_and_faqs lives at POST
https://{shop}/api/mcp -- NOT the split the spec's own module summary describes, see
SHOPIFY_NOTES.md "Disagreement #1". Every call goes through a per-store rate limiter,
TTL cache, and circuit breaker (I12), and is logged (store, tool, latency, status) to
support I11/I12 audits (spec section 5.1.3).
"""

import asyncio
import json
import time
from typing import Any

import httpx

from bigbrain.common.logging import get_logger
from bigbrain.shopify.cache import TTLCache
from bigbrain.shopify.circuit import CircuitBreaker, CircuitOpenError
from bigbrain.shopify.models import ShopCart, ShopPolicyAnswer, ShopProduct
from bigbrain.shopify.ratelimit import TokenBucket

logger = get_logger("shopify.client")

_POLICY_TOOLS = {"search_shop_policies_and_faqs"}


class ShopifyClientError(Exception):
    """Base for all errors this client raises."""


class ShopifyAPIError(ShopifyClientError):
    """The store answered with a JSON-RPC error, or a retryable error persisted past
    max_retries."""

    def __init__(self, code: int | str, message: str, data: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.data = data or {}
        super().__init__(f"Shopify API error {code}: {message}")


class ShopifyForbiddenError(ShopifyClientError):
    """The store returned 403 -- I12: stop immediately, do not retry."""


class ShopifyCircuitOpenError(ShopifyClientError):
    """The circuit breaker is open for this store; the call was not attempted."""


class ShopifyMCPClient:
    """One client per Shopify store. Construct with just `shop_domain` and
    `agent_profile_url` for sane defaults; pass explicit rate_limiter/cache/
    circuit_breaker/http_client for testing or tuning.
    """

    def __init__(
        self,
        shop_domain: str,
        agent_profile_url: str,
        *,
        rate_limiter: TokenBucket | None = None,
        cache: TTLCache | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        http_client: httpx.AsyncClient | None = None,
        cache_ttl_s: float = 300.0,
        rate_per_sec: float = 1.0,
        failure_threshold: int = 3,
        cooldown_s: float = 60.0,
        timeout_s: float = 10.0,
        max_retries: int = 3,
        backoff_base_s: float = 0.5,
    ) -> None:
        self.shop_domain = shop_domain
        self.agent_profile_url = agent_profile_url
        self.ucp_url = f"https://{shop_domain}/api/ucp/mcp"
        self.policy_url = f"https://{shop_domain}/api/mcp"
        self.rate_limiter = rate_limiter or TokenBucket(rate=rate_per_sec)
        self.cache = cache or TTLCache(ttl_s=cache_ttl_s)
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=failure_threshold, cooldown_s=cooldown_s
        )
        self._http = http_client or httpx.AsyncClient(timeout=timeout_s)
        self._owns_http = http_client is None
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self._next_id = 0

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    def _endpoint_url(self, tool: str) -> str:
        if tool in _POLICY_TOOLS:
            return self.policy_url
        return self.ucp_url

    def _next_request_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _meta(self) -> dict:
        return {"ucp-agent": {"profile": self.agent_profile_url}}

    async def _sleep_backoff(self, attempt: int, retry_after: str | None) -> None:
        if retry_after is not None:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = self.backoff_base_s * (2 ** (attempt - 1))
        else:
            delay = self.backoff_base_s * (2 ** (attempt - 1))
        await asyncio.sleep(delay)

    async def _call(
        self, tool: str, arguments: dict[str, Any], *, cache_key: str | None = None
    ) -> dict:
        """Low-level JSON-RPC tools/call, with rate limiting, caching, circuit
        breaking, retry-with-backoff, and logging. Returns the raw `result` dict.
        Raises ShopifyCircuitOpenError, ShopifyForbiddenError, or ShopifyAPIError.
        """
        if cache_key is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.info("shopify call cache_hit store=%s tool=%s", self.shop_domain, tool)
                return cached

        try:
            self.circuit_breaker.check()
        except CircuitOpenError as exc:
            raise ShopifyCircuitOpenError(f"circuit open for {self.shop_domain}") from exc

        url = self._endpoint_url(tool)
        body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": self._next_request_id(),
            "params": {"name": tool, "arguments": arguments},
        }

        attempt = 0
        while True:
            await self.rate_limiter.acquire()
            start = time.monotonic()
            try:
                response = await self._http.post(url, json=body)
            except httpx.HTTPError as exc:
                latency_ms = (time.monotonic() - start) * 1000
                logger.warning(
                    "shopify call transport_error store=%s tool=%s latency_ms=%.1f error=%s",
                    self.shop_domain,
                    tool,
                    latency_ms,
                    exc,
                )
                attempt += 1
                if attempt > self.max_retries:
                    self.circuit_breaker.record_failure()
                    raise ShopifyClientError(f"transport error calling {tool}: {exc}") from exc
                await self._sleep_backoff(attempt, None)
                continue

            latency_ms = (time.monotonic() - start) * 1000
            status = response.status_code

            if status == 403:
                logger.warning(
                    "shopify call forbidden store=%s tool=%s latency_ms=%.1f",
                    self.shop_domain,
                    tool,
                    latency_ms,
                )
                self.circuit_breaker.force_open()
                raise ShopifyForbiddenError(f"{self.shop_domain} returned 403 for {tool}")

            if status == 429 or status >= 500:
                logger.warning(
                    "shopify call retryable_error store=%s tool=%s status=%d "
                    "latency_ms=%.1f attempt=%d",
                    self.shop_domain,
                    tool,
                    status,
                    latency_ms,
                    attempt,
                )
                attempt += 1
                if attempt > self.max_retries:
                    self.circuit_breaker.record_failure()
                    raise ShopifyAPIError(
                        status, f"{status} from {tool} after {self.max_retries} retries"
                    )
                await self._sleep_backoff(attempt, response.headers.get("retry-after"))
                continue

            payload = response.json()
            if "error" in payload:
                err = payload["error"]
                logger.warning(
                    "shopify call rpc_error store=%s tool=%s code=%s latency_ms=%.1f",
                    self.shop_domain,
                    tool,
                    err.get("code"),
                    latency_ms,
                )
                self.circuit_breaker.record_failure()
                raise ShopifyAPIError(
                    err.get("code", status), err.get("message", ""), err.get("data")
                )

            logger.info(
                "shopify call ok store=%s tool=%s status=%d latency_ms=%.1f",
                self.shop_domain,
                tool,
                status,
                latency_ms,
            )
            self.circuit_breaker.record_success()
            result = payload.get("result", {})
            if cache_key is not None:
                self.cache.set(cache_key, result)
            return result

    async def list_tools(self, *, policy_endpoint: bool = False) -> list[dict]:
        url = self.policy_url if policy_endpoint else self.ucp_url
        await self.rate_limiter.acquire()
        body = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": self._next_request_id(),
            "params": {},
        }
        response = await self._http.post(url, json=body)
        payload = response.json()
        if "error" in payload:
            raise ShopifyAPIError(
                payload["error"].get("code", response.status_code),
                payload["error"].get("message", ""),
            )
        return payload.get("result", {}).get("tools", [])

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

        arguments = {"meta": self._meta(), "catalog": catalog}
        cache_key = f"search_catalog:{self.shop_domain}:{query}:{cursor}:{limit}"
        result = await self._call("search_catalog", arguments, cache_key=cache_key)
        products = [ShopProduct.model_validate(p) for p in result.get("products", [])]
        return products, result.get("pagination", {})

    async def lookup_catalog(self, ids: list[str]) -> list[ShopProduct]:
        arguments = {"meta": self._meta(), "catalog": {"ids": ids}}
        cache_key = f"lookup_catalog:{self.shop_domain}:{','.join(sorted(ids))}"
        result = await self._call("lookup_catalog", arguments, cache_key=cache_key)
        return [ShopProduct.model_validate(p) for p in result.get("products", [])]

    async def get_product(
        self, product_id: str, *, selected: list[dict] | None = None
    ) -> ShopProduct:
        catalog: dict[str, Any] = {"id": product_id}
        if selected is not None:
            catalog["selected"] = selected
        arguments = {"meta": self._meta(), "catalog": catalog}
        cache_key = f"get_product:{self.shop_domain}:{product_id}:{selected}"
        result = await self._call("get_product", arguments, cache_key=cache_key)
        return ShopProduct.model_validate(result["product"])

    async def search_policies(self, query: str) -> list[ShopPolicyAnswer]:
        """No structuredContent for this tool (SHOPIFY_NOTES.md, Disagreement #2) --
        parse content[0].text as JSON ourselves."""
        arguments = {"query": query}
        cache_key = f"search_policies:{self.shop_domain}:{query}"
        result = await self._call("search_shop_policies_and_faqs", arguments, cache_key=cache_key)
        text = result["content"][0]["text"]
        answers_raw = json.loads(text)
        return [ShopPolicyAnswer.model_validate(a) for a in answers_raw]

    async def create_cart(self, line_items: list[dict]) -> ShopCart:
        """Never cached -- this is a mutating call (creates a real cart on the store)."""
        arguments = {"meta": self._meta(), "cart": {"line_items": line_items}}
        result = await self._call("create_cart", arguments)
        return ShopCart.model_validate(result.get("cart", result))

    async def update_cart(self, cart_id: str, line_items: list[dict]) -> ShopCart:
        """Never cached -- this is a mutating call."""
        arguments = {"meta": self._meta(), "cart": {"id": cart_id, "line_items": line_items}}
        result = await self._call("update_cart", arguments)
        return ShopCart.model_validate(result.get("cart", result))
