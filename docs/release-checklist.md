# Release Checklist

Use this checklist before publishing a public preview or tagged release.

For the first GitHub public preview, also follow
[docs/publish-runbook.md](publish-runbook.md).

## Required Gates

Run these commands from the repository root:

```bash
uvx ruff check .
uv run --extra dev pytest -q
uv build
uvx pip-audit
```

Then verify the built wheel in a clean environment:

```bash
tmpvenv="$(mktemp -d)/venv"
tmpwork="$(mktemp -d)"
python -m venv "$tmpvenv"
. "$tmpvenv/bin/activate"
python -m pip install --upgrade pip
python -m pip install dist/*.whl
cd "$tmpwork"
research-ledger --help
research-ledger init --scope-title "smoke test" --scope-description "temporary release smoke workspace"
printf '# Claim\n' > claim.md
research-ledger record claim.md --type claim
research-ledger seal --label smoke
research-ledger verify
research-ledger report
research-ledger export-disclosure --output disclosure.md
research-ledger export-bundle --output audit-bundle.zip
```

## Manual Review

- Confirm `README.md` and `README.zh-Hant.md` quickstart commands match the CLI.
- Confirm `SPEC.md` matches the event signing and hashing implementation.
- Confirm `SECURITY.md` still lists known limitations honestly.
- Confirm `CHANGELOG.md` has an entry for the release.
- Confirm no `.research-ledger/private_key.pem` or real research snapshots are committed.
- Confirm no local caches, `.DS_Store`, `__pycache__`, `.pyc`, virtualenvs, or build artifacts are staged.
- Confirm public `docs/reviews/` files are intentionally retained and do not include local paths, private prompts, or private reviewer source files.
- Confirm recorded PDF or attachment snapshots are not published or bundled without sharing rights.
- Confirm `SECURITY.md` names the intended private reporting channel.
- Confirm generated `dist/` artifacts were produced from the current tree.
- Confirm dependency changes were intentional and `uv.lock` was updated.

## Release Notes

Release notes should include:

- New CLI commands and behavior changes.
- Verification guarantees and limitations.
- Migration or compatibility notes.
- Known security limitations.
- Test and build evidence.
