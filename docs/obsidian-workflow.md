# Obsidian Workflow Design

Research Ledger can be used with Obsidian today because it records ordinary
files inside a workspace. The intended integration model is one research project
per ledger root, not one large mixed vault treated as a single implicit ledger.

## Goals

- Preserve the signed first-run `scope.json` as the research boundary.
- Support common AI-assisted research note types without requiring an Obsidian
  plugin.
- Keep PDFs and licensed attachments safe by preferring source-check or manifest
  cards unless full bytes are needed.
- Make recorded and unrecorded vault areas clear to reviewers.

## Recommended Folder Boundary

For a large vault, create one folder per research project and initialize the
ledger there:

```text
My Vault/
  Thesis Project/
    .research-ledger/
    01-claims/
    02-source-checks/
    03-ai-outputs/
    04-adjudication/
    05-drafts/
    06-disclosure/
    attachments/
```

Initialize with an explicit scope:

```bash
cd "My Vault/Thesis Project"
research-ledger init \
  --scope-title "AI-assisted thesis research" \
  --scope-description "Claims, source checks, AI outputs, adjudication notes, drafts, and disclosure notes for this thesis project." \
  --include . \
  --exclude attachments/private
```

If the ledger root is the whole vault, the scope must use precise `--include`
and `--exclude` paths. This is less clear for third-party review and should not
be the default.

## Note Types

Use ordinary Markdown cards and record them with semantic event types:

```bash
research-ledger record 01-claims/001-research-question.md --type claim
research-ledger record 02-source-checks/001-citation-check.md --type source_check
research-ledger record 03-ai-outputs/001-model-response.md --type ai_output
research-ledger record 04-adjudication/001-human-decision.md --type adjudication
research-ledger record 05-drafts/chapter-1.md --type draft
research-ledger record 06-disclosure/ai-use-disclosure.md --type disclosure
```

The CLI intentionally accepts plain files. Obsidian-specific metadata should
remain in Markdown front matter or body text so the recorded snapshot is still
portable.

## PDFs and Attachments

PDFs are normal research sources, but recording a PDF stores a full immutable
snapshot and audit bundles include recorded snapshots.

For ordinary literature PDFs, prefer a `source_check` or manifest card:

```markdown
# Source Check

- Citation:
- Local file:
- DOI or URL:
- Retrieval date:
- File size:
- SHA-256:
- Notes:
```

Record the PDF bytes only when the exact local copy is material to the audit.
Before sharing an audit bundle, check whether recorded snapshots include
licensed, private, or advisor-only files.

## Lifecycle Events

Obsidian renames and deletes files frequently. Use lifecycle events to stop
stale drift warnings while preserving history:

```bash
research-ledger rename 01-claims/old.md 01-claims/new.md --reason "Obsidian rename"
research-ledger delete 05-drafts/obsolete.md --reason "merged into current draft"
```

After a rename, record the new path if the renamed note's current content should
become a new snapshot.

## Review Workflow

Before sharing:

```bash
research-ledger verify
research-ledger seal --label review
research-ledger export-disclosure --output 06-disclosure/ai-use-disclosure.md
research-ledger record 06-disclosure/ai-use-disclosure.md --type disclosure
research-ledger export-bundle --output audit-bundle.zip
```

Reviewers should read `scope.json` first, then the disclosure draft, then event
records and snapshots. A clean ledger does not prove that every in-scope step
was recorded; it shows that recorded artifacts have not changed under the local
trust model.

## Future Plugin Shape

An optional Obsidian plugin can later provide commands for:

- initializing a project ledger with a scope wizard,
- recording the active note with a selected event type,
- showing verify warnings inside Obsidian,
- generating disclosure drafts,
- warning before bundling recorded PDFs or private attachments.

The plugin should call the CLI or reuse the same file format. It should not
create a separate ledger format.

