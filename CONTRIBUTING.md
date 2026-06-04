# Contributing

## Local Setup

```bash
uv sync --extra dev
uv run --extra dev pytest -q
uvx ruff check .
uv run research-ledger --help
```

## Development Rules

- Keep the CLI local-first.
- Do not add network calls to core verification.
- Add tests before changing ledger format, signature payloads, or hash behavior.
- Update `SPEC.md` for any schema or canonicalization change.
- Treat `.research-ledger/private_key.pem` as secret material.
- Do not commit generated caches, local virtual environments, build artifacts,
  real research snapshots, or private review material.

## Adding Event Types

New event types should be additive. They must not change the meaning of existing
fields. If a new field is required for verification, bump `schema_version`.

## Test Expectations

Run:

```bash
uv run --extra dev pytest -q
uvx ruff check .
uv build
```

Changes touching cryptography, hashing, or verification should include negative
tests that fail before the fix.
