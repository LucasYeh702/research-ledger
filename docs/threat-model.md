# Threat Model

## Security Claim

Research Ledger provides tamper-evident local records for research workflow
events under a local trust model. It does not make research claims true, prevent
plagiarism, create legal evidence, or replace human source verification.

## Protected Against

- Editing a recorded event in `events.jsonl`
- Reordering events
- Modifying a recorded snapshot after recording
- Breaking the hash chain between events
- Forging an event without access to the signing key
- Re-signing an event with a different public key while keeping the original
  ledger metadata
- Tampering with the signed first-run scope declaration
- Adding unknown event fields outside the signed schema
- Tampering with seal Merkle roots
- Accidentally recording files outside the workspace

## Not Protected Against

- A key holder rewriting the full ledger from genesis
- A user deleting the full ledger before sharing it
- False claims intentionally entered by the researcher
- AI hallucinations that were recorded but never checked
- A researcher declaring a misleading scope
- A researcher omitting events for in-scope work
- Ambiguous mixed workspaces where recorded and unrecorded notes are not clearly
  separated by the scope declaration
- Accidental disclosure of recorded PDF or attachment snapshots through an audit
  bundle
- Lost or stolen private keys
- Private key loss without a recovery workflow
- Replacing the full ledger metadata, genesis file, and event log before any
  external anchoring exists
- Backdating based on local system time

## Adversary Model

| Actor | Capability | Expected result |
|---|---|---|
| Accidental user | Edits live notes after recording | Verification should warn |
| Accidental user | Edits snapshots or event rows | Verification should fail |
| Local attacker without private key | Edits ledger or files | Verification should fail |
| Local attacker with private key | Re-signs or rewrites the full ledger | Not fully protected without external anchoring |
| Dishonest author | Selectively omits events or declares a misleading scope | Not protected |

## Future Hardening

- OpenTimestamps for external timestamp anchoring
- Git signed tags for release and milestone anchoring
- Optional hardware-backed key storage
- Third-party verification bundles with Merkle proofs
