# BigBrain

Prototype of AI-agent-mediated shopping over real Shopify stores: a buyer agent turns a
human's need into a structured, encrypted intent, broadcasts it to a category channel,
collects sealed private offers from merchant agents, negotiates on multiple attributes,
and hands the human a shortlist and a Shopify checkout URL. The human always decides and
always pays.

Read `CLAUDE.md` first: it is the entry point for any session working in this repo. The
full design and experiment requirements live in `../BIGBRAIN_SPEC.md`.

## Setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync          # create .venv, resolve dependencies into uv.lock
make test        # pytest (live tests are skipped by default)
make lint        # ruff check .
make check       # lint + tests
```

`uv run pytest` and `uv run ruff check .` pass offline with no API keys. Tests marked
`@pytest.mark.live` hit real Shopify stores and are deselected by default (`-m 'not live'`
in `pyproject.toml`); opt in with `uv run pytest -m live`.

## Repository layout

The authoritative layout is spec section 10. Short version:

| Path | Contents |
| --- | --- |
| `src/bigbrain/` | The package: `common`, `protocol`, `transport`, `shopify`, `profiler`, `taxonomy`, `directory`, `broker`, `mailbox`, `buyer`, `merchant`, `llm`, `payments`, `ui` |
| `tests/` | `unit/`, `integration/`, `property/`, `invariants/`, `live/` |
| `docs/` | `PROGRESS.md`, `DECISIONS.md`, `ARCHITECTURE.md`, `SHOPIFY_NOTES.md`, `FINDINGS.md` |
| `data/`, `fixtures/`, `sim/`, `experiments/` | Taxonomy subset, store panel, recorded Shopify cassettes, synthetic market, experiment configs |

## Status

See `docs/PROGRESS.md`.
