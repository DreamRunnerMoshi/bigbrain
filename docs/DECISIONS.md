# Decisions (ADRs)

Context -> decision -> consequences, one entry per decision. Add entries whenever the spec
is ambiguous or the stack changes (CLAUDE.md working rules 3 and the spec section 3 rule).

## ADR-001 - Category taxonomy standard

**Context.** The prototype needs a canonical product category system to key pub/sub
channels. Two candidates: Google Product Taxonomy and Shopify's Standard Product Taxonomy.

**Decision.** Use Shopify Standard Product Taxonomy (open source, `shopify/product-taxonomy`
on GitHub) as the canonical channel-ID source, since merchants are Shopify stores. Keep
Google Product Taxonomy as a secondary cross-mapping for future non-Shopify merchants,
using Shopify's published mapping where available.

**Consequences.** Directory and profiler code key everything off Shopify taxonomy IDs;
Google IDs are optional/best-effort on intents and never required.

## ADR-002 - Tooling scaffold: uv + hatchling src layout, ruff, pytest

**Context.** M0 needs a runnable empty test suite and a passing lint, reproducible from a
lock file, on Python 3.12 (spec section 3). Python 3.12 is not the interpreter installed on
the machine (3.13 is), so the version must be pinned by the tooling, not by the shell.

**Decision.**

- `pyproject.toml` is a uv-managed, *packaged* project: `[build-system]` uses
  `hatchling.build` with `packages = ["src/bigbrain"]`, `requires-python = ">=3.12"`.
  `uv sync` therefore installs the package editable into `.venv`, so `import bigbrain`
  works in tests and a future `bigbrain` Typer CLI can be exposed as a console script
  without further config.
- `uv.lock` is committed; `.venv/` is not (see `.gitignore`).
- Test tooling lives in the `[dependency-groups].dev` group (pytest, pytest-asyncio,
  hypothesis, ruff). Runtime dependencies from spec section 3 (pydantic, fastapi, httpx,
  pynacl, typer, pandas, matplotlib, anthropic, etc.) are declared up front in
  `[project.dependencies]` so any milestone can start using them without a tooling PR.
- pytest is configured with `testpaths = ["tests"]`, `pythonpath = ["src"]`, and
  `addopts = "-ra -m 'not live'"`, with the `live` marker declared. Live Shopify tests are
  therefore skipped by default and opt-in via `uv run pytest -m live` (CLAUDE.md: live mode
  is opt-in; everything else must run offline).
- ruff: `line-length = 100`, `target-version = "py312"`, `src = ["src", "tests"]`,
  lint rules `E, W, F, I, B, UP, C4, SIM`, isort `known-first-party = ["bigbrain"]`.
  Formatting is the Ruff formatter (`make format`), checked with `make format-check`.
- Every `src/bigbrain/<module>/` and `tests/<kind>/` directory is a package with a
  one-line docstring `__init__.py` naming that subpackage's responsibility (verbatim from
  spec section 10's repo-layout comments), so test module names are unambiguous
  (`tests.unit.test_placeholder`) and subpackages are self-describing on import.

**Consequences.**

- `uv run pytest -q` and `uv run ruff check .` are the gates (also `make check`); CI and
  the milestone definition of done can rely on them.
- The `live` marker must be applied to every test that touches the network, or it will run
  in CI and fail without credentials.
- Adding a runtime dependency beyond spec section 3's list is a normal edit to
  `[project.dependencies]` plus `uv lock`/`uv sync`; changing the *stack* needs a new ADR.
- Python 3.12 is fetched by uv on first `uv sync` if it is not installed locally; the
  lock file keeps the resolution reproducible either way.

## ADR-003 - Audit log is hash-chained now, Ed25519-signed later

**Context.** BIGBRAIN_SPEC.md §7 and open problem #7 call for a signed, append-only audit
log, but signing keys don't exist until the M1 crypto module (`common/crypto.py`).

**Decision.** Implement a hash-chained JSONL append-only audit log in M0 as tamper-evident
storage (each entry stores `prev_hash` and its own `entry_hash = sha256(canonical_json)`).
Add real Ed25519 signatures over each entry once `common/crypto.py` exists in M1, without
changing the file format — hash chaining stays, a signature field gets added.

**Consequences.** M0's audit log proves an entry wasn't silently altered after the fact
once you have the whole file, but a compromised process could still fabricate a consistent
chain from scratch. That gap closes in M1.
