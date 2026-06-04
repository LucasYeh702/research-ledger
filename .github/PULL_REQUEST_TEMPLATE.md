## Summary

- 

## Verification

- [ ] `uv run --extra dev pytest -q`
- [ ] `uvx ruff check .`
- [ ] `uv build`
- [ ] Wheel smoke test, if packaging or CLI behavior changed

## Risk Notes

- [ ] This change does not alter ledger format, signature payloads, or hash behavior.
- [ ] If it does, `SPEC.md`, tests, and migration notes were updated.
- [ ] No private research material, snapshots, keys, local paths, or raw agent logs are included.
