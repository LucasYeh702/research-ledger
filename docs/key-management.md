# Key Management

Research Ledger v0.1 uses one local Ed25519 private key per ledger. The key is
stored at:

```text
.research-ledger/private_key.pem
```

This file is secret material. Do not commit it, publish it, or include it in
review bundles.

## Backup Guidance

Back up `private_key.pem` securely if you need to keep writing to the same
ledger identity after moving machines. Losing the private key does not invalidate
existing events, but it prevents new events from being signed with the same key.

Recommended practice:

- Store the key in an encrypted backup.
- Keep the backup separate from public audit bundles.
- Record the public key fingerprint (`key_id`) in a trusted note or release
  record.

## If The Key Is Lost

If `private_key.pem` is lost:

- Existing events can still be verified with `ledger.json`, `genesis.json`,
  `events.jsonl`, and `snapshots/`.
- New events cannot be appended under the same signing identity.
- Start a new ledger and document the continuity break in your disclosure notes.

Research Ledger intentionally refuses to silently regenerate a replacement key
when `ledger.json` already exists.

## If The Key Is Compromised

If the private key may have been copied or exposed:

- Stop using that ledger for new events.
- Preserve the old ledger for verification and investigation.
- Start a new ledger with a new key.
- Document the compromise window and the new `key_id`.

Research Ledger v0.1 does not support key rotation or revocation. A future
version should add signed key rotation events and revocation metadata.

## Audit Bundles

Use `research-ledger export-bundle --output audit-bundle.zip` when sharing a
ledger for third-party verification. Audit bundles exclude `private_key.pem`.
