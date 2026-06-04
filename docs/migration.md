# Migration and Obsidian Vault Moves

Research Ledger is designed to survive moving an entire vault or workspace to a
different computer when the ledger directory, event snapshots, and recorded
working-note relative paths are preserved.

## Safe Move

Verification should still pass when all of the following are true:

- The entire workspace is copied.
- `.research-ledger/` is copied with the notes.
- `.research-ledger/scope.json` is copied with the ledger.
- `.research-ledger/snapshots/` is copied with the ledger.
- `.research-ledger/private_key.pem` is copied securely.
- Recorded files keep the same relative paths inside the workspace.

Changing the absolute folder path is allowed. Event records store paths relative
to the ledger root when the file is inside the workspace.

Working notes may differ from their recorded snapshots. This produces a warning,
not a verification failure.

## Unsafe Move

Verification can fail after migration when:

- Only Obsidian notes are moved and `.research-ledger/` is not moved.
- `.research-ledger/snapshots/` is missing or changed.
- `.research-ledger/ledger.json`, `.research-ledger/genesis.json`, or
  `.research-ledger/scope.json` is replaced.
- `.research-ledger/private_key.pem` is lost.
  The tool will not silently regenerate a replacement key for an existing
  ledger.

Verification may warn after migration when:

- iCloud, Git, an editor, or a sync tool changes a working note's line endings
  from LF to CRLF.
- A tool normalizes Unicode content or rewrites Markdown formatting in a working
  note.
- A working note is renamed or moved without recording a new event.

Filename Unicode normalization is handled separately from content hashing. During
working-file drift checks, the verifier first tries the exact recorded relative
path, then searches path components by NFC-normalized filenames. This protects
common macOS/iCloud vault moves where `café.md` may be represented with composed
or decomposed Unicode filename bytes. It does not normalize file content bytes.

Use lifecycle events to mark intentional changes:

```bash
research-ledger delete notes/obsolete.md --reason "merged into newer note"
research-ledger rename notes/old.md notes/new.md --reason "Obsidian rename"
```

## Hash Policy

Research Ledger stores a raw-byte snapshot for each recorded event and hashes
that snapshot by raw bytes. It does not normalize newlines or Unicode for
snapshot content. This is intentional: a changed byte means the recorded
artifact is no longer identical to the original recorded artifact.

Working files are also compared against their recorded snapshot. A mismatch is a
drift warning, not a failure.

Ledger JSON canonicalization is separate from content hashing.

## Recommended Practice

Before migrating:

```bash
research-ledger verify
research-ledger export-disclosure --output disclosure-before-move.md
```

After migrating:

```bash
research-ledger verify
research-ledger report
```

If verification warns with `working file changed since snapshot`, inspect whether
the sync or editor changed the working note bytes during migration. If
verification fails with `snapshot hash mismatch`, the recorded snapshot itself
has changed and the ledger should not be trusted until investigated.
