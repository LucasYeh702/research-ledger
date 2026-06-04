# Dependency Policy

Research Ledger keeps runtime dependencies small because it handles security-
sensitive provenance data.

## Runtime Dependencies

Current runtime dependencies:

- `cryptography`: Ed25519 key generation, signing, and verification.
- `pydantic`: strict schema models and validation.
- `typer`: command-line interface.

## Development Dependencies

Current development dependency:

- `pytest`: regression and red-team tests.

Linting and ad hoc audits may use `uvx` tools so they do not become runtime
dependencies.

## Update Policy

- Prefer small, well-maintained dependencies.
- Avoid adding network or AI dependencies to the core verifier.
- Treat dependency changes as security-relevant.
- Run the release checklist after dependency updates.
- Keep `uv.lock` updated with tested dependency versions.

## Audit Guidance

Before a public release, run:

```bash
uvx pip-audit
```

If an advisory affects a runtime dependency, document the impact and update the
dependency before release when a fix is available.
