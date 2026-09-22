# Progress

One entry per milestone, newest first (CLAUDE.md working rule 4). Milestones and their
acceptance criteria are spec section 11.

## M0 - Skeleton and tooling (in progress)

Done so far:

- Repo skeleton, directory layout, and `CLAUDE.md` were already in place before this entry.
- `pyproject.toml`: uv-managed Python 3.12 project, src layout, hatchling build backend,
  pytest config (`tests/`, `src` on `pythonpath`, `live` marker deselected by default) and
  ruff config (line length 100, target py312).
- Dev toolchain in the `dev` dependency group: pytest, pytest-asyncio, hypothesis, ruff.
  Runtime dependencies from spec section 3 (pydantic, fastapi, uvicorn, websockets, httpx,
  respx, vcrpy, pynacl, typer, pandas, matplotlib, anthropic) are declared in
  `[project.dependencies]` up front. `uv.lock` is committed.
- `Makefile` targets: `sync`, `test`, `lint`, `format`, `format-check`, `check`, `clean`,
  `help`. `make test` is the M0 entry point.
- `.gitignore` (venv, caches, build output, experiment `results/`, local env files).
- `README.md`: setup, test/lint commands, layout summary.
- `__init__.py` for every package under `src/bigbrain/` and every test directory.
- `tests/unit/test_placeholder.py`: the only test file, asserting the package and its
  subpackages import. Replace it once M1 code lands.
- `docs/`: `PROGRESS.md`, `DECISIONS.md` (ADR-000), `ARCHITECTURE.md`, `SHOPIFY_NOTES.md`
  (stub, nothing verified yet), `FINDINGS.md` (stub).

Verification: `uv run pytest -q` -> 1 passed, 0 deselected; `uv run ruff check .` -> clean.

Still open for M0 completion (not part of the tooling scaffold):

- `common/` config, logging, and append-only audit log modules (spec section 5.1 of
  CLAUDE.md's stack summary; milestone M0 lists them).

Next: M1 - wire format and crypto (envelope, canonical JSON, signatures, payload models,
state machine) plus the I7 tamper tests.
