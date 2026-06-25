# Scope Declaration

Research Ledger starts with a signed scope declaration. This makes the first
question explicit: what research-note boundary is this ledger intended to cover?

The declaration is written to:

```text
.research-ledger/scope.json
```

It is created by `research-ledger init`, signed with the ledger's Ed25519 key,
verified by `research-ledger verify`, included in `export-disclosure`, and
included in third-party audit bundles.

## Why This Exists

An event chain can show that recorded events were linked and signed. It cannot,
by itself, tell a reviewer what the ledger was supposed to cover.

For AI-assisted thesis work, this matters. A researcher may have several
projects, private notes, raw PDFs, advisor-only material, and published drafts
inside the same vault. The verifier needs to know which files were inside the
declared research-note boundary and which were outside it.

## Recommended Scope Model

Prefer one ledger root per research project.

For thesis or article work, the clearest setup is:

```text
research-project/
  .research-ledger/
  notes/
  sources/
  drafts/
  disclosures/
```

This avoids making reviewers guess whether unrecorded notes in a large vault
were out of scope, accidentally omitted, or selectively left unrecorded.

Using one large Obsidian vault as the ledger root is possible, but it requires a
more careful `scope.json`. If some entries in the same vault are recorded and
others are not, the scope declaration and disclosure draft must make that
boundary explicit. Otherwise, mixed recorded/unrecorded material can create a
misleading audit narrative.

Good patterns:

- one thesis, article, or research case per ledger;
- include only the project folder, not the whole personal vault;
- keep literature PDFs and other source attachments inside the project when
  they are part of the research workflow;
- use explicit exclusions for private, advisor-only, non-research, or
  non-shareable folders;
- keep unrecorded scratch material outside the declared project boundary when
  possible.

Avoid:

- declaring an entire vault when only one project is actually being recorded;
- mixing several unrelated research projects under one ledger;
- leaving in-scope folders partially recorded without explaining the recording
  policy;
- treating `scope.json` as proof of exhaustive capture.

For PDF and attachment storage choices, see [storage-policy.md](storage-policy.md).

## Recommended First Run

```bash
research-ledger init \
  --scope-title "AI-assisted legal thesis research" \
  --scope-description "Research notes, source checks, AI outputs, human adjudication notes, drafts, and disclosure notes for this thesis project." \
  --include "thesis-notes" \
  --exclude "thesis-notes/private"
```

Use repeatable `--include` and `--exclude` options when needed.

## What The Declaration Means

The scope declaration means:

- these paths are eligible research-note areas for this ledger;
- excluded paths should not be interpreted as missing records;
- later event records and disclosure reports should be read against this
  declared boundary;
- the declaration itself has not been modified if `verify` passes.

It does not mean:

- every in-scope file has been recorded;
- every research step was captured;
- the recorded claims are true;
- the author has fully complied with institutional or publisher rules.

## Suggested Fields In Plain Language

Use the title to name the research line, not the tool:

```text
AI-assisted thesis research
```

Use the description to say what is covered:

```text
本 ledger 涵蓋本論文的研究命題、來源查核、AI 輸出、人類裁判、草稿與 AI 使用揭露。
```

Use includes and excludes to define the Obsidian or filesystem boundary:

```text
include: thesis-notes
exclude: thesis-notes/private
```

## Review Guidance

When reviewing a ledger, check `scope.json` before reading events. A useful
review order is:

1. Read the scope declaration.
2. Verify the ledger.
3. Review event type counts.
4. Inspect source checks and human adjudication events.
5. Read the disclosure draft with the declared scope in mind.
