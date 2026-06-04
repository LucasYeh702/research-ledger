# Security Policy

## Supported Versions

Research Ledger is currently a pre-release project. Only the latest `main`
branch and tagged `0.x` releases are supported.

## Reporting Security Issues

Do not open a public issue for a suspected vulnerability before maintainers have
had time to review it. Preferred reporting channel for the public repository is
GitHub Security Advisories. If private reporting is not available yet, open a
minimal public issue that says "security report available" without exploit
details.

## Known Limitations

- Research Ledger is tamper-evident, not tamper-proof.
- It does not prove that a claim is true or that a source is reliable.
- It does not guarantee that a researcher recorded every relevant step.
- Working notes may change after recording. Verification treats that as a
  warning when the recorded snapshot is intact.
- Delete and rename events only mark working-note lifecycle state. They do not
  remove historical snapshots.
- A private key holder can rewrite a full local ledger unless an external anchor
  already exists.
- v0.1 does not support key rotation or revocation.
- Local timestamps are not trusted external time.
- v0.1 only records files inside the ledger workspace.
- v0.1 refuses to silently regenerate missing private keys for existing ledgers.
- Audit bundles include recorded snapshots; recorded PDFs or attachments may
  require separate sharing permission.

## Secret Material

`.research-ledger/private_key.pem` is secret material. Do not commit it, publish
it, or include it in review bundles.

For backup, key loss, and suspected key compromise guidance, see
[docs/key-management.md](docs/key-management.md).

`.research-ledger/snapshots/` contains recorded research artifacts. It may
include sensitive notes or source excerpts. Do not publish it unless the content
is safe to disclose.

`record` rejects paths outside the workspace to reduce accidental leakage of
unrelated local files into snapshots.

## External Anchoring

OpenTimestamps and Git signed tags are not implemented in v0.1. Until external
anchoring exists, long-term timestamp claims should be treated as local claims.
