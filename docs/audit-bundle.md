# Audit Bundles

Audit bundles are ZIP files intended for third-party verification of immutable
Research Ledger records. They are created with:

```bash
research-ledger export-bundle --output audit-bundle.zip
```

The bundle includes:

- `.research-ledger/ledger.json`
- `.research-ledger/genesis.json`
- `.research-ledger/scope.json`
- `.research-ledger/events.jsonl`
- `.research-ledger/snapshots/`
- `.research-ledger/seals/`
- `REPORT.md`
- `VERIFY.md`

The bundle intentionally excludes:

- `.research-ledger/private_key.pem`
- mutable working notes outside `.research-ledger/`
- virtual environments, caches, and Git metadata

The bundle includes recorded snapshots. If a recorded snapshot is a PDF or other
attachment, the bundle includes that snapshot. Check sharing rights before
sending bundles to third parties.

## Verification

After extracting a bundle, run:

```bash
research-ledger verify --no-working-tree
```

`--no-working-tree` skips drift checks for mutable working notes that are not
part of the bundle. It still verifies:

- the signed genesis trust root
- the signed research scope declaration
- event signatures
- event hash chain
- snapshot content hashes
- schema and canonicalization versions
- seal Merkle roots

## Limitations

An audit bundle does not prove that the researcher recorded every relevant step,
that every in-scope note was recorded, that a claim is true, or that AI use was
fully disclosed. Without external anchoring, a key holder who controls all local
files can still rewrite a new internally consistent ledger.
