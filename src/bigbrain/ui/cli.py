"""Typer CLI entrypoint (spec section 10 target commands). This task implements
`bigbrain shopify probe` and `bigbrain shopify record`; other subcommands
(`bigbrain buy`, `bigbrain profile`, etc.) land with their own milestones.
"""

import asyncio
from pathlib import Path

import typer
import yaml

from bigbrain.common.config import Settings, load_config
from bigbrain.shopify.client import ShopifyClientError, ShopifyMCPClient

app = typer.Typer(help="BigBrain CLI")
shopify_app = typer.Typer(help="Shopify integration commands")
app.add_typer(shopify_app, name="shopify")


def _resolve_profile_url(settings: Settings) -> str:
    if not settings.shopify_agent_profile_url:
        typer.secho(
            "Warning: no shopify_agent_profile_url configured (see "
            "common/config.py Settings, or pass --config pointing at a YAML file "
            "that sets it) -- live calls will fail with a 422 from Shopify "
            "(docs/SHOPIFY_NOTES.md: the agent profile is server-fetched and "
            "enforced).",
            fg=typer.colors.YELLOW,
        )
        return ""
    return settings.shopify_agent_profile_url


@shopify_app.command("probe")
def probe(
    shop_domain: str = typer.Argument(..., help="Store domain, e.g. allbirds.com"),  # noqa: B008
    config_path: Path | None = typer.Option(  # noqa: B008
        None, "--config", help="Path to a YAML config file (see common/config.py)"
    ),
) -> None:
    """tools/list on both endpoints; report health and which tools exist (spec
    section 5.2 step 1, section 10)."""
    settings = load_config(config_path)
    profile_url = _resolve_profile_url(settings)

    async def _run() -> None:
        client = ShopifyMCPClient(shop_domain, profile_url)
        try:
            typer.echo(f"Probing {shop_domain} ...")
            try:
                ucp_tools = await client.list_tools()
                typer.secho(f"  /api/ucp/mcp: OK, {len(ucp_tools)} tools", fg=typer.colors.GREEN)
                for t in ucp_tools:
                    typer.echo(f"    - {t['name']}")
            except ShopifyClientError as exc:
                typer.secho(f"  /api/ucp/mcp: RESTRICTED ({exc})", fg=typer.colors.RED)

            try:
                policy_tools = await client.list_tools(policy_endpoint=True)
                typer.secho(f"  /api/mcp: OK, {len(policy_tools)} tools", fg=typer.colors.GREEN)
                for t in policy_tools:
                    typer.echo(f"    - {t['name']}")
            except ShopifyClientError as exc:
                typer.secho(f"  /api/mcp: RESTRICTED ({exc})", fg=typer.colors.RED)
        finally:
            await client.aclose()

    asyncio.run(_run())


@shopify_app.command("record")
def record(
    shop_domain: str = typer.Option(..., "--shop", help="Store domain, e.g. allbirds.com"),  # noqa: B008
    script_path: Path = typer.Option(..., "--script", help="YAML file listing queries to record"),  # noqa: B008
    fixtures_dir: Path = typer.Option(Path("fixtures/shopify"), "--fixtures-dir"),  # noqa: B008
    config_path: Path | None = typer.Option(None, "--config"),  # noqa: B008
) -> None:
    """Record real Shopify responses into fixtures/shopify/<shop>/cassette.jsonl
    (spec section 5.1.5). Script format (YAML), all keys optional:

    \b
      search_catalog: ["query one", "query two"]
      get_product: ["gid://shopify/Product/123"]
      search_policies: ["what is your return policy"]
    """
    settings = load_config(config_path)
    profile_url = _resolve_profile_url(settings)
    script = yaml.safe_load(script_path.read_text(encoding="utf-8")) or {}
    cassette_path = Path(fixtures_dir) / shop_domain / "cassette.jsonl"

    async def _run() -> None:
        client = ShopifyMCPClient(shop_domain, profile_url, record_path=cassette_path)
        try:
            for query in script.get("search_catalog", []):
                typer.echo(f"search_catalog({query!r}) ...")
                try:
                    await client.search_catalog(query=query)
                except ShopifyClientError as exc:
                    typer.secho(f"  failed: {exc}", fg=typer.colors.RED)

            for product_id in script.get("get_product", []):
                typer.echo(f"get_product({product_id!r}) ...")
                try:
                    await client.get_product(product_id)
                except ShopifyClientError as exc:
                    typer.secho(f"  failed: {exc}", fg=typer.colors.RED)

            for question in script.get("search_policies", []):
                typer.echo(f"search_policies({question!r}) ...")
                try:
                    await client.search_policies(question)
                except ShopifyClientError as exc:
                    typer.secho(f"  failed: {exc}", fg=typer.colors.RED)
        finally:
            await client.aclose()

    asyncio.run(_run())
    typer.secho(f"Recorded to {cassette_path}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
