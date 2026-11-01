# Phase 13A + 13B implementation

Phase 13 extends Phase 12 with multi-region trust continuity and a bounded AI security
control plane.

## Phase 13A — multi-region trust federation and continuity

### Deployment regions and trust links

Organization-scoped `DeploymentRegion` records describe a region without storing cloud
credentials. A `RegionTrustLink` connects two regions through:

- source and peer SPIFFE trust domains;
- a pinned peer-bundle SHA-256 digest;
- an allowlisted HTTPS bundle endpoint;
- optional approved OpenID Federation trust-anchor context;
- explicit operator verification state.

A remote bundle never becomes trusted simply because it can be fetched. Verification
checks the public-only JWK shape, digest pin and endpoint policy before the link enters
`verified` state. Runtime SPIFFE verification remains the responsibility of SPIRE.

### Cross-cloud workload identity

`CrossCloudWorkloadBinding` records the intended SPIFFE-to-cloud exchange without
storing a cloud secret. AWS deployments can exchange a JWT-SVID with
`AssumeRoleWithWebIdentity`; Azure deployments can federate a JWT-SVID through Microsoft
Entra workload identity federation. See
`docs/phase13-cross-cloud-workload-identity.md`.

### Tamper-evident transparency log

The application-level transparency ledger is an append-only SHA-256 hash chain:

- each entry commits to the previous entry hash;
- canonical JSON is used before hashing;
- the verifier recomputes the entire organization/log chain;
- database row locking serializes concurrent appends;
- delete operations are not exposed through the Phase 13 API.

This is a tamper-evident application ledger, not a substitute for a Merkle-tree
transparency service such as Rekor. Release artifacts are separately eligible for
keyless Sigstore/Cosign signing and public transparency through the release workflow.

### Trust-continuity snapshots

Snapshots commit to:

- active deployment regions;
- verified regional trust links and bundle digests;
- federation trust-anchor digests;
- workload-identity policies;
- public HSM/key metadata only.

Snapshot payloads are encrypted at rest, SHA-256 hashed and can be Ed25519-signed.
Restore is never automatic. A snapshot must validate, then a human/platform administrator
records restore approval. The runbook requires independent verification before any
cloud/federation trust is changed.

## Phase 13B — AI gateway, injection resistance, confidential RAG and agent permissions

### Model gateway

The Phase 13 model gateway is the only reference path intended for governed AI inference.
A policy can restrict:

- models;
- tasks;
- data categories;
- input size;
- maximum output tokens;
- whether a signed/passed model release is required.

Tool execution is disabled in this gateway. User and retrieved content are placed in
untrusted-data boundaries, not injected into system/developer instructions.

### Prompt-injection defense in depth

`phase13_security.py` contains a dependency-light deterministic scanner that can run in
CI independently from the model/database stack. It detects common instruction-override,
system-prompt extraction, credential-exfiltration and tool-abuse patterns.

Detection is intentionally not treated as a complete security boundary. The stronger
controls are architectural:

- no tools in the model gateway;
- allowlisted model/task/data categories;
- signed release/evaluation gates;
- confidential RAG with approved documents only;
- blocked retrieved documents are excluded from model context;
- agent actions are separately authorized through permission manifests.

Prompt/event audit records store digests and metadata rather than raw candidate content.

### Confidential RAG

RAG context comes only from previously approved knowledge. Each retrieved document is
scanned as untrusted content. Injection-like documents are excluded, and the audit record
stores document digests, counts and release/policy metadata instead of full context.

This repository does not claim that a pattern scanner can solve prompt injection.
Security depends primarily on constraining the actions that compromised model text could
cause.

### Signed model/evaluation releases

`ModelRelease` binds:

- exact model/snapshot identifier;
- prompt/workflow version;
- successful `ModelEvalRun`;
- policy digest;
- SLSA baseline metadata;
- optional Ed25519 release signature;
- human approval state.

The release workflow also signs immutable image digests with Cosign. The application
release signature and container/provenance signature solve different problems and are
kept separate.

### Autonomous-agent permission manifests

`AgentPermissionManifest` is default-deny. An action must be explicitly allowed and not
explicitly denied. The policy can constrain:

- action names;
- data categories;
- destination hosts;
- number of external calls;
- actions requiring human approval.

Agent action decisions are audited. There is no catch-all permission and denied actions
take precedence over allowed actions.

## Operational boundaries

Phase 13 does not:

- auto-trust a remote SPIFFE/federation endpoint;
- store cross-cloud exchanged bearer credentials;
- auto-restore trust after a region failure;
- give the model gateway arbitrary tools;
- claim that prompt-injection scanning is sufficient by itself;
- allow unsigned/failed-evaluation releases when the policy requires a signed release;
- permit autonomous-agent behavior without an approved manifest;
- turn the local transparency hash chain into a claimed public transparency-log service.

Production deployments should keep SPIRE, cloud IAM, release signing, key management and
security-controller credentials outside ordinary application administration paths.
