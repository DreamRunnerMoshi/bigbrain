# Progress

One entry per milestone, newest first (CLAUDE.md working rule 4). Milestones and their
acceptance criteria are spec section 11.

## M0 - Skeleton and tooling (done)

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
- `docs/`: `PROGRESS.md`, `DECISIONS.md` (ADR-001, ADR-002), `ARCHITECTURE.md`, `SHOPIFY_NOTES.md`
  (stub, nothing verified yet), `FINDINGS.md` (stub).
- `common/config.py`: strict pydantic v2 `Settings` with the `RuntimeMode` enum covering the
  four modes of spec section 3, plus `load_config()` over an optional YAML file (defaults when
  the path is None/missing/empty, pydantic `ValidationError` on bad values). Default mode is
  REPLAY -- offline, no API keys. `pyyaml` added to `[project.dependencies]` for this.
- `common/logging.py`: `setup_logging()` configures the `bigbrain` logger (never the root
  logger) with a single stderr handler and ISO-8601 UTC timestamps, idempotently;
  `get_logger(name)` returns `bigbrain.<name>`. Callers must never log decrypted intent/offer
  plaintext (spec section 7); the structured audit trail is below.
- `common/audit.py`: append-only, hash-chained JSONL audit log (`AuditLog`, `AuditEvent`,
  `GENESIS_HASH`), one `<session_id>.jsonl` per session, each entry chaining to the previous
  `entry_hash = sha256(canonical JSON)`; `verify_chain()` walks the file. Unsigned for now --
  Ed25519 signatures land in M1 per ADR-003.
- `common/__init__.py` re-exports the three modules' public names.
- `tests/unit/test_config.py`, `test_logging.py`, `test_audit.py`: config loading and
  validation, logging idempotency, chain building across re-opened logs, tamper detection.

Verification: `uv run pytest -q` -> 15 passed, 0 deselected; `uv run ruff check .` -> clean.

Next: M1 - wire format and crypto (envelope, canonical JSON, signatures, payload models,
state machine) plus the I7 tamper tests.
