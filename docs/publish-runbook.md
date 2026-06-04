# Public Preview Publish Runbook

This runbook is for the first GitHub public preview of Research Ledger.

## Preconditions

- `git status --short --branch` is clean.
- `uv run --extra dev pytest -q` passes.
- `uvx ruff check .` passes.
- `uv build` succeeds.
- `uvx pip-audit` reports no known vulnerabilities.
- Wheel smoke test succeeds in a fresh virtual environment.
- Secret and local-path scans show no private key, token, `.env`, `.DS_Store`,
  `.pyc`, local absolute path, raw agent transcript, or build/cache artifact.

## Recommended GitHub Settings

- Visibility: public preview.
- Default branch: `main`.
- License: Apache-2.0.
- Security advisories: enabled.
- Dependabot alerts: enabled.
- Actions: enabled.
- Releases: do not publish PyPI package until the first public feedback pass is
  complete.

## Create And Push

Using GitHub CLI:

```bash
gh repo create research-ledger \
  --public \
  --source=. \
  --remote=origin \
  --description "Local-first tamper-evident ledger for AI-assisted research workflows."

git push -u origin main
```

If the repository already exists:

```bash
git remote add origin git@github.com:<owner>/research-ledger.git
git push -u origin main
```

## Post-Push Checks

- Confirm GitHub Actions runs the test workflow successfully.
- Confirm `README.md`, `README.zh-Hant.md`, `SECURITY.md`, and `LICENSE`
  render correctly on GitHub.
- Confirm no generated `dist/`, `cache/`, `.research-ledger/`, `.venv/`, or
  Python cache files appear in the repository browser.
- Create the first issue for stale write lock recovery.
- Create the first issue for external timestamp anchoring design, such as
  OpenTimestamps or another append-only transparency witness.

## Suggested First Issues

### Stale Write Lock Recovery

If a process is killed while holding `.research-ledger/write.lock`, future
writes currently fail after timeout until the user removes the lock. Implement
cross-platform stale lock recovery with tests.

### External Timestamp Anchoring

Design an optional external anchoring flow for seals. The first version should
preserve local-first verification and avoid making OpenTimestamps or any single
server a required trust dependency.

### Obsidian Integration

Design an optional Obsidian-facing workflow that records AI-assisted research
events while preserving the first-run scope declaration and one-research-project
boundary model.
