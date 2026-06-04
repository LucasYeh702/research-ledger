from __future__ import annotations

import zipfile
from pathlib import Path

from research_ledger.disclosure import build_disclosure_report, render_markdown
from research_ledger.ledger import Ledger


VERIFY_INSTRUCTIONS = """# Research Ledger Audit Bundle

This bundle contains the public verification material for a Research Ledger:

- `.research-ledger/ledger.json`
- `.research-ledger/genesis.json`
- `.research-ledger/scope.json`
- `.research-ledger/events.jsonl`
- `.research-ledger/snapshots/`
- `.research-ledger/seals/`
- `REPORT.md`

It intentionally excludes `.research-ledger/private_key.pem`.

To verify the immutable ledger and snapshots after extraction:

```bash
research-ledger verify --no-working-tree
```

`--no-working-tree` skips mutable working-note drift checks. It still verifies
the genesis trust root, event signatures, hash chain, snapshot hashes, schema
versions, signed scope declaration, and seal integrity.
"""


def export_audit_bundle(ledger: Ledger, output: Path) -> Path:
    result = ledger.verify(check_working_files=False)
    if not result.ok:
        details = "; ".join(result.issues)
        raise ValueError(f"cannot export invalid ledger: {details}")

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = render_markdown(build_disclosure_report(ledger))

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_required_file(archive, ledger.metadata_path, ledger.root)
        _write_required_file(archive, ledger.genesis_path, ledger.root)
        _write_required_file(archive, ledger.scope_path, ledger.root)
        _write_required_file(archive, ledger.events_path, ledger.root)
        _write_tree(archive, ledger.snapshots_dir, ledger.root)
        _write_tree(archive, ledger.seals_dir, ledger.root)
        archive.writestr("REPORT.md", report)
        archive.writestr("VERIFY.md", VERIFY_INSTRUCTIONS)

    return output


def _write_required_file(archive: zipfile.ZipFile, path: Path, root: Path) -> None:
    archive.write(path, path.relative_to(root).as_posix())


def _write_tree(archive: zipfile.ZipFile, directory: Path, root: Path) -> None:
    if not directory.exists():
        return
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name.startswith(".pending-"):
            continue
        archive.write(path, path.relative_to(root).as_posix())
