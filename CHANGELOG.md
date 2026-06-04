# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-04

### Added

- Local-first append-only JSONL event log with hash chain
- Ed25519 key pair generation and event signing
- Signed genesis trust root binding ledger ID, public key, and tool metadata
- Signed first-run `scope.json` declaration for research-note boundaries
- `init` command to bootstrap a new research ledger
- `init --scope-title`, `--scope-description`, `--include`, and `--exclude`
  options for declaring project scope
- `record` command to record research events (claim, ai_output, source_check, adjudication, etc.) with immutable snapshots
- `delete` and `rename` lifecycle events for working-note path management
- Deterministic canonical JSON serialization (sorted keys, compact separators, LF normalization, NaN/Infinity rejection)
- SHA-256 content hashing with streaming I/O for large files
- `seal` command to compute Merkle-root seals over event hashes (domain-separated, odd-leaf promotion)
- `verify` command with comprehensive integrity checks (hash chain, signatures, schema versions, key trust, content hashes, seal integrity)
- Differentiated exit codes for verification results (0=pass, 1=warnings, 2=tamper, 3=malformed, 4=snapshot missing)
- Working-file drift detection with warning-only semantics
- `report` command for short ledger status summaries
- `export-disclosure` command for AI-use disclosure drafts in Markdown and JSON
- README sections for what the tool can and cannot prove, plus a 3-minute demo
- CI gates for ruff, pytest, package build, and wheel install smoke
- `verify --no-working-tree` for third-party audit bundles without mutable notes
- `export-bundle` command for ZIP audit bundles that exclude private key material
- `scope.json` included in disclosure reports and audit bundles
- Release checklist, key management guide, and audit bundle documentation
- Scope declaration guide and storage / attachment policy documentation
- Dependency policy and Dependabot configuration
- Path traversal prevention (rejects files outside workspace)
- Automatic `.gitignore` inside `.research-ledger/` to exclude `private_key.pem`
- Private key file permissions set to 0o600
- Unicode NFC/NFD-aware working file resolution
- Pydantic v2 models with `extra="forbid"` to reject unknown event fields

### Security

- Private key stored locally without encryption (documented limitation)
- No key rotation support in v0.1 (documented limitation)
- Local timestamps are not externally anchored (documented limitation)
- Seals are not individually signed (documented limitation)
- `record` rejects symbolic links and internal `.research-ledger/` files
- Mutating operations use a local write lock; seals are written via temp file and replace
- Disclosure exports include a non-certification disclaimer
- PDF and attachment snapshot sharing risks are documented

### Changed

- CI wheel smoke now exercises scope declaration creation.
- README and SPEC now recommend one ledger root per research project.
- README and docs clarify that PDFs are normal research sources, but full PDF
  snapshots should be recorded deliberately because audit bundles include them.

[0.1.0]: #010---2026-06-04
