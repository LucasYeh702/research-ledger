# Roadmap

Research Ledger starts small on purpose: a local-first, tamper-evident ledger
for AI-assisted research workflows.

## v0.1 Public Preview

- Local ledger initialization with signed genesis and scope declaration.
- Explicit event recording for claims, source checks, AI outputs, adjudication,
  drafts, disclosure notes, delete events, and rename events.
- Immutable per-event snapshots.
- Hash-chain and Ed25519 signature verification.
- Merkle seal creation and verification.
- Audit bundle export without private key material.
- Markdown and JSON AI-use disclosure drafts.
- Red-team tests for migration, working-note drift, path safety, permissions,
  malformed ledgers, and snapshot tampering.

## Near-Term Hardening

- Stale write-lock recovery after interrupted writes.
- Optional external timestamp anchoring design for seals.
- Better audit-bundle redaction guidance for licensed PDFs and private sources.
- Additional examples for Obsidian-based research projects.
- More explicit compatibility notes for cloud-sync providers.

## Later Directions

- Optional Obsidian workflow integration.
- Key rotation and revocation design.
- External witness or transparency-log integrations.
- Richer disclosure templates for academic, legal, and policy research.
- Machine-readable verification reports for CI and archival workflows.

## Non-Goals For v0.1

- Proving that a research claim is true.
- Certifying source reliability.
- Guaranteeing that all research steps were recorded.
- Preventing a private-key holder from rewriting all local history without an
  external anchor.
- Replacing institutional AI-use, research ethics, legal evidence, or publisher
  rules.
