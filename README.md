# Research Ledger

Research Ledger is a local-first, open-source audit ledger for AI-assisted academic
research. It records claims, source checks, AI outputs, human adjudication, draft
snapshots, and disclosure notes as tamper-evident events.

It does not prove that a claim is true, that a source is reliable, or that the
author recorded every step. It detects post-record modification under an explicit
local trust model.

## What This Can Help Show

- A recorded snapshot has not changed since it was recorded.
- Events are linked in order through a hash chain.
- Events were signed by the ledger's local Ed25519 key.
- Local Merkle seals summarize recorded event hashes.
- Working notes may continue to evolve; drift is reported as a warning.

## What This Does Not Prove

Research Ledger does not prove that a claim is true, that a source is reliable,
that all research steps were recorded, that AI use was fully disclosed, or that
the ledger satisfies any legal, institutional, or publisher evidence standard.

Without external anchoring, a person who controls the private key and all local
files can rewrite an internally consistent ledger.

The project is intentionally small in its first release:

- append-only JSONL event log
- signed genesis trust root
- signed first-run scope declaration
- immutable per-event snapshots
- delete and rename lifecycle events
- deterministic canonical JSON hashing
- hash chain verification
- Ed25519 signatures
- daily or milestone seals with Merkle roots
- seal integrity verification
- local verification reports
- Markdown and JSON AI-use disclosure drafts

## 3-minute Demo

```bash
mkdir rl-demo
cd rl-demo
research-ledger init

cat > claim.md <<'EOF'
# Claim
AI-assisted legal research needs process-level provenance, not only final citations.
EOF

research-ledger record claim.md --type claim
research-ledger verify

printf "\nRevised after source check.\n" >> claim.md
research-ledger verify

research-ledger record claim.md --type claim
research-ledger seal --label demo
research-ledger report
research-ledger export-disclosure --output disclosure.md
```

For local development inside this repository, prefix commands with `uv run`.

## Quick Start

```bash
uv sync --extra dev
uv run research-ledger init \
  --scope-title "AI-assisted thesis notes" \
  --scope-description "Research notes, source checks, AI outputs, adjudication notes, drafts, and disclosure notes for this thesis project." \
  --include examples/obsidian-vault \
  --exclude examples/obsidian-vault/private
uv run research-ledger record examples/obsidian-vault/研究留痕範例/001-命題.md --type claim
uv run research-ledger seal
uv run research-ledger verify
uv run research-ledger report
uv run research-ledger export-disclosure --output disclosure.md
```

## First-run Scope Declaration

`research-ledger init` creates a signed `.research-ledger/scope.json` file. This
declares the research-note boundary the ledger is intended to cover before any
research events are recorded.

The declaration should answer:

- What research project or thesis line does this ledger cover?
- Which workspace paths are in scope?
- Which paths are explicitly out of scope?
- What recording policy should reviewers assume?

The scope declaration is signed and verified, and audit bundles include it. It
does not prove that every in-scope step was recorded. It defines the eligible
research-note boundary so later event records, disclosures, and third-party
reviews can be interpreted in context.

Best practice: use one ledger root per research project. If a large Obsidian
vault contains some notes that are recorded and some that are not, keep the
ledger scope to the project folder and declare exclusions explicitly. Otherwise,
reviewers may confuse out-of-scope notes with selectively omitted records.

## PDFs and Attachments

PDFs are normal research sources and may be kept inside the project. Research
Ledger can record them directly, but `record` stores a full immutable snapshot
of the file. For ordinary literature PDFs, prefer recording a source-check or
manifest card with citation metadata, local path, retrieval date, file size, and
checksum. Record the PDF bytes themselves when the exact local copy matters to
the audit trail.

Audit bundles include recorded snapshots. If a recorded snapshot is a licensed,
copyrighted, private, or advisor-only PDF, the bundle will contain that PDF
snapshot. See [docs/storage-policy.md](docs/storage-policy.md).

## Working Note Changes

Working notes are allowed to evolve. `record` stores an immutable snapshot under
`.research-ledger/snapshots/`; later edits to the live note produce a warning,
not a failure.

If a note is intentionally removed or renamed, record that lifecycle event:

```bash
uv run research-ledger delete notes/obsolete.md --reason "merged into newer note"
uv run research-ledger rename notes/old.md notes/new.md --reason "Obsidian rename"
```

This stops stale missing-file drift warnings while preserving the original
snapshot history.

## Disclosure Export

`export-disclosure` turns the current ledger into an AI-use disclosure draft. It
summarizes the declared research scope, event types, recorded files,
verification status, seal roots, and known limitations.

```bash
uv run research-ledger export-disclosure
uv run research-ledger export-disclosure --format json --output disclosure.json
```

The exporter does not certify research quality. It gives researchers a
structured draft they can review, edit, and submit according to their own
institutional requirements.

## Threat Model

Research Ledger is tamper-evident, not tamper-proof. It can detect edited,
reordered, or deleted events and modified snapshots when the verifier has the
expected ledger metadata, genesis record, and signing key binding. Working notes
may continue to evolve; if they differ from a recorded snapshot, verification
reports a warning rather than a failure. Local records alone cannot prevent a key
holder from rewriting the entire ledger. External anchoring such as
OpenTimestamps can be added to strengthen timestamp claims.

See [SPEC.md](SPEC.md), [docs/threat-model.md](docs/threat-model.md), and
[SECURITY.md](SECURITY.md) before relying on this tool. If you use Obsidian or
sync vaults between computers, read [docs/migration.md](docs/migration.md).
For third-party review, see [docs/audit-bundle.md](docs/audit-bundle.md). For
private key handling, see [docs/key-management.md](docs/key-management.md).
For first-run research boundary design, see
[docs/scope-declaration.md](docs/scope-declaration.md).
For PDFs and larger attachments, see
[docs/storage-policy.md](docs/storage-policy.md).
For release and dependency hygiene, see [docs/release-checklist.md](docs/release-checklist.md),
[docs/dependency-policy.md](docs/dependency-policy.md), and
[docs/publish-runbook.md](docs/publish-runbook.md).

For project support and community norms, see [SUPPORT.md](SUPPORT.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), [ROADMAP.md](ROADMAP.md), and
[CITATION.cff](CITATION.cff).

## License

Code is licensed under Apache-2.0.
