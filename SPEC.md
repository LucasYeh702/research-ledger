# Research Ledger Format Specification

Version: 0.1

## Scope

This specification defines the local ledger format used by Research Ledger
v0.1. The format is designed for tamper-evident research workflow records. It is
not a legal evidence standard and does not prove that recorded claims are true.

## Storage Layout

```text
.research-ledger/
  .gitignore
  ledger.json
  genesis.json
  scope.json
  private_key.pem
  events.jsonl
  snapshots/
  seals/
```

`private_key.pem` is local secret material and must not be committed.
`.research-ledger/.gitignore` must ignore `private_key.pem`.

## Versions

Every genesis event, scope declaration, and research event includes:

- `schema_version`: currently `0.1`
- `canonicalization_version`: currently `research-ledger-c14n-v1`

Unknown schema or canonicalization versions must fail verification, including
unsupported versions declared in `ledger.json`.

## Canonicalization

Research Ledger v0.1 canonical JSON:

- UTF-8 encoded
- sorted object keys
- compact separators
- LF-normalized string values inside ledger JSON
- metadata values accept JSON-compatible primitives plus `datetime`, `date`, and
  `Path` values, which are normalized to ISO-8601 strings or POSIX-style paths
- string object keys only
- rejects `NaN`, `Infinity`, and `-Infinity`

Snapshot content hashes use raw bytes. They do not normalize text newlines or
Unicode content.

Recorded PDFs and other attachments are hashed and snapshotted by the same raw
byte policy as Markdown notes. The format does not currently deduplicate large
attachments or store deltas between repeated snapshots.

Working files are mutable. Moving a workspace to another computer preserves
verification when `.research-ledger/`, snapshots, and relative paths are
preserved. If a working file differs from its recorded snapshot, verification
returns a warning.

When checking mutable working files, verification first tries the exact recorded
relative path and then falls back to NFC-normalized filename matching. This
prevents decomposed/composed Unicode filename differences from creating false
drift warnings after vault migration.

## Trust Root

`research-ledger init` creates a signed `genesis.json` file that binds:

- `ledger_id`
- `schema_version`
- `canonicalization_version`
- actor id
- Ed25519 public key
- public key fingerprint (`key_id`)
- tool name and version

The first recorded research event links its `previous_event_hash` to the signed
genesis event hash.

## Scope Declaration

`research-ledger init` creates a signed `scope.json` file that declares the
research-note boundary for the ledger before any research events are recorded.
The scope declaration binds:

- `ledger_id`
- `schema_version`
- `canonicalization_version`
- declaration type (`scope`)
- creation timestamp
- human-readable title
- plain-language description
- included workspace-relative paths
- excluded workspace-relative paths
- recording policy
- signed genesis event hash
- Ed25519 public key
- public key fingerprint (`key_id`)
- tool name and version

The signature and `event_hash` rules are the same as genesis: sign the complete
payload excluding `signature` and `event_hash`, then hash the payload including
`signature` and excluding `event_hash`.

The declaration is governance metadata. It defines the eligible research-note
boundary for interpreting later events and disclosure reports. It does not prove
that every in-scope file or research step was recorded.

Recommended practice is one ledger root per research project. Implementations do
not require this, but a mixed workspace with partially recorded and unrecorded
research notes should use explicit included and excluded paths. Otherwise,
reviewers may confuse out-of-scope material with selectively omitted records.

## Key Binding

`ledger.json` stores the trusted Ed25519 public key and key id. Verification
requires each event's `author_public_key` and `key_id` to match `ledger.json`.
An event re-signed with a different key fails verification.

In v0.1, `key_id` is the SHA-256 fingerprint of the raw Ed25519 public key,
encoded as `ed25519-sha256:<hex>`. The field name is kept as `key_id` in JSON
because it is the stable key binding identifier used by the verifier.

Research Ledger v0.1 does not support key rotation. Future versions should add a
signed key rotation event.

If `ledger.json` already exists but `private_key.pem` is missing, `init` must not
silently generate a replacement key. The existing ledger is not writable until
the original key is restored or an explicit key recovery workflow exists.

If events already exist but `genesis.json` is missing, `init` must not recreate a
new genesis record.

## Event Hash and Signature

For each research event:

1. Build the signing payload from the complete event object excluding
   `signature` and `event_hash`.
2. Canonicalize the signing payload.
3. Sign those canonical bytes with Ed25519 and store the Base64 signature in
   `signature`.
4. Build the event-hash payload from the complete event object including
   `signature` but excluding `event_hash`.
5. Canonicalize the event-hash payload.
6. Compute `event_hash` as `sha256:<hex>` from those canonical bytes.

Verification must independently rebuild both payloads. Any change to signed
fields, `signature`, or `event_hash` must fail verification.

Each event includes:

- `content_path`: relative path to the mutable working file when available
- `snapshot_path`: relative path to the immutable recorded snapshot
- `content_hash`: SHA-256 hash of the snapshot raw bytes

Events must reject fields outside the schema. Unknown fields are treated as a
malformed event.

`record` only accepts regular files inside the ledger workspace. Directories,
symbolic links, paths outside the workspace, and files inside `.research-ledger/`
are rejected.

`record` writes snapshots and computes file hashes with streaming I/O. It must
not read large target files into memory as a single byte string.

## Lifecycle Events

Research Ledger v0.1 supports lifecycle events for working-note paths:

- `delete`: records that a mutable working file path was intentionally removed.
- `rename`: records that a mutable working file path was intentionally renamed.

Lifecycle events have immutable synthetic snapshots containing canonical JSON of
the lifecycle action. They suppress future working-file drift warnings for the
old path, but they do not delete or modify historical snapshots.

For `rename`, the `content_path` is the old path and `metadata.new_path` is the
new path. Users should `record` the new path if they want the renamed working
file's current content to become a new content snapshot.

## Event Ordering

Research events use `sequence` starting from `1`. Each event contains
`previous_event_hash`. For the first event this equals the signed genesis event
hash. Later events link to the previous research event hash.

Verification warns when event timestamps move backwards. Timestamp order is a
local consistency signal, not trusted external time.

## Seal

`research-ledger seal` computes a Merkle root over the current ordered list of
research event hashes. The seal payload is signed by the ledger's Ed25519 key
and has its own `event_hash` using the same signature and hash rules as genesis,
scope declarations, and research events. Inclusion proof and external timestamp
anchoring are future work.

The Merkle tree uses domain-separated leaf and internal-node hashing. Odd leaves
are promoted to the next layer rather than duplicated, so `[A, B, C]` and
`[A, B, C, C]` cannot collapse to the same root through last-leaf duplication.

`verify` checks seal files for valid schema, matching ledger id, matching public
key and key id, valid seal signature, matching seal event hash, event hash list,
event count, tip hash, and Merkle root. Unsigned seal files fail verification.

## Verification Exit Codes

| Exit code | Meaning |
|---:|---|
| 0 | Verification passed |
| 1 | Verification passed with warnings, such as working file drift |
| 2 | Tamper detected or signature invalid |
| 3 | Malformed ledger or invalid genesis trust root |
| 4 | Referenced snapshot file missing |

Uninitialized ledgers and malformed metadata should exit with code `3` without a
Python traceback.

`verify --no-working-tree` skips mutable working-file drift checks for archive
or audit-bundle verification. It still checks genesis, the signed scope
declaration, signatures, hash chain, snapshots, schema versions, and seals.

## Audit Bundles

`export-bundle` writes a ZIP archive containing public verification material:

- `.research-ledger/ledger.json`
- `.research-ledger/genesis.json`
- `.research-ledger/scope.json`
- `.research-ledger/events.jsonl`
- `.research-ledger/snapshots/`
- `.research-ledger/seals/`
- `REPORT.md`
- `VERIFY.md`

Bundles must exclude `.research-ledger/private_key.pem`.

Bundles include recorded snapshots. If a recorded snapshot is a PDF or other
large attachment, that file is included in the bundle. Users should choose
between full attachment snapshots and source-check/manifest records based on the
audit need and sharing rights.

## Disclosure Export

`export-disclosure` reads the local ledger and produces a disclosure draft in
Markdown or JSON. The report contains:

- ledger id and schema information
- genesis hash and trusted key id
- research scope declaration
- verification result
- event type counts
- event summaries
- seal summaries
- explicit limitations

The disclosure export is not itself written into the ledger in v0.1. Users who
need to preserve a disclosure artifact should save the output and record that
file as a `disclosure` event.
