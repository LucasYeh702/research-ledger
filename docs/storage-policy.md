# Storage and Attachment Policy

Research Ledger can record PDFs and other attachments. They are normal research
materials, especially for legal and academic writing.

The storage question is not whether PDFs are allowed. The question is how much
of the reference material should become immutable ledger snapshots, and how much
should be represented through source-check records, manifests, and checksums.

## Snapshot Cost Model

`record` stores a full byte-for-byte snapshot of the target file under:

```text
.research-ledger/snapshots/
```

It does not currently use delta compression, deduplication, or external object
storage. Approximate ledger growth is therefore:

```text
sum(recorded snapshot file sizes) + events.jsonl + seals + metadata
```

Markdown notes are usually small and can be recorded frequently. Large PDFs,
images, transcripts, datasets, and exported bundles should be recorded more
deliberately.

## Recommended Practice

Use different recording strategies by artifact type.

| Artifact | Recommended strategy |
|---|---|
| Markdown research notes | Record directly and frequently. |
| Claim, source-check, adjudication, draft, disclosure cards | Record directly. |
| Key PDFs whose exact bytes matter to the audit trail | Record directly, usually once per stable version. |
| Ordinary literature PDFs kept for reading and reference | Keep in the project source folder; record a source-check or manifest card with metadata and checksum. |
| Licensed, copyrighted, private, or advisor-only attachments | Keep locally, but avoid including them in public audit bundles unless sharing is permitted. |
| Large datasets or media files | Prefer manifest/checksum records unless the audit use case requires full immutable snapshots. |

## PDF Guidance

PDFs are often central research sources. A good PDF workflow is:

1. Store the PDF inside the research project folder.
2. Create a `source_check` Markdown card with citation metadata, local path,
   original URL or DOI, retrieval date, file size, and SHA-256 checksum.
3. Record the `source_check` card.
4. Record the PDF itself only when preserving the exact local copy is important
   for the audit trail.
5. If the PDF is replaced by a newer version, record the new PDF once and
   explain the version change in a new source-check card.

This preserves the research trail without forcing every literature PDF into
every third-party audit bundle.

## Audit Bundle Caution

`export-bundle` currently includes all recorded snapshots. If a recorded
snapshot is a PDF, the audit bundle will include that PDF snapshot.

Before sharing an audit bundle externally, check whether recorded attachments
may be legally or ethically shared. For restricted materials, prefer recording a
source-check card or manifest instead of the PDF bytes, or share the bundle only
with an authorized reviewer.

## Future Improvements

Useful future features include:

- hash-only attachment events;
- content-addressed blob storage with deduplication;
- bundle profiles that can include or omit attachment snapshots;
- explicit `record-attachment` and `record-manifest` commands;
- size warnings before recording large files.
