# External Timestamp Anchoring Design

Research Ledger is local-first. Local seals prove that a set of recorded event
hashes had a specific Merkle root at local seal time, but they do not prove that
the seal existed before an externally verifiable time.

External anchoring should strengthen timestamp claims without making any single
network service part of the core trust model.

## Goals

- Anchor seal commitments, not private research content.
- Preserve offline local verification.
- Support more than one witness type over time.
- Make failed or missing external anchors a warning, not a local integrity
  failure.
- Include anchor artifacts in audit bundles when they are safe to share.

## Non-Goals

- Proving that a research claim is true.
- Proving that all research activity was recorded.
- Replacing institutional evidence, ethics, or publisher rules.
- Making OpenTimestamps, a blockchain, GitHub, or any single service mandatory.

## Anchor Commitment

The first anchorable object should be a seal commitment:

```text
ledger_id
schema_version
seal_label
seal_created_at
event_count
tip_event_hash
merkle_root
```

The commitment hash should be computed from canonical JSON using the same
canonicalization rules as ledger events. The external witness receives only the
commitment hash, not note contents, snapshots, event metadata, private keys, or
research titles beyond what is already included in a chosen public artifact.

## Suggested Local Files

External anchors should live under:

```text
.research-ledger/anchors/
```

Each anchor record should include:

- the referenced seal file,
- the local commitment hash,
- the witness type, such as `opentimestamps`, `git_tag`, or `transparency_log`,
- witness-specific proof data or references,
- creation time according to the local machine,
- verification status and last verified time when checked.

Anchor records are public verification metadata and may be included in audit
bundles. They must not contain private keys or raw source material.

## Future CLI Shape

The first implementation can be explicit and optional:

```bash
research-ledger anchor create --seal latest --type opentimestamps
research-ledger anchor verify
research-ledger export-bundle --output audit-bundle.zip
```

If no network is available, local `verify` should still validate the ledger,
seals, signatures, hash chain, and snapshots. Anchor verification should report
missing, pending, failed, or untrusted witnesses separately from local ledger
integrity.

## Verification Semantics

Anchor verification should answer:

- Does the anchor record refer to an existing seal?
- Does the seal still verify locally?
- Does the anchor commitment match the current seal data?
- Does the witness proof verify according to that witness's rules?
- What external time, if any, does the witness support?

If a witness is unavailable, the verifier should report an anchor warning rather
than failing local ledger verification.

## Threat Model Impact

External anchoring can reduce the risk that a key holder rewrites the entire
ledger after the anchor time. It does not prevent rewriting future unanchored
events, selective omission, misleading scope declarations, false claims, or
private-key misuse before anchoring.

Reviewers should treat external anchors as additional timestamp evidence for a
specific seal commitment, not as certification of research quality.

