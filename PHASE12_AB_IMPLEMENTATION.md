# Phase 12A + 12B implementation

Phase 12 extends the Phase 11 career architecture with federated trust and a bounded
zero-trust/runtime-security control plane.

## Phase 12A — trust-framework federation

### OpenID Federation 1.1

The implementation targets the OpenID Federation 1.1 Final Specification approved
in May 2026.

The reference implementation deliberately uses an administrator-reviewed trust graph:

- trust anchors are organization-scoped and platform-admin approved;
- entity public JWKS are stored explicitly;
- entity self-statements are signature checked;
- subordinate statements are signature checked against the registered parent;
- trust chains are depth bounded and cycle checked;
- trust only succeeds when the path terminates at an enabled approved anchor;
- resolving or registering an entity does not automatically make it trusted.

This is safer than dynamically trusting arbitrary metadata URLs. If remote discovery is
added later, use a strict host allowlist, no redirects, egress controls, timeouts, response
size limits, and the same signature/trust-chain validation before accepting metadata.

### Wallet attestation trust chains

Wallet attestations:

- require an `x5c` certificate chain;
- validate certificate validity periods and chain signatures;
- must chain to an installed organization trust anchor;
- validate the attestation JWT signature and registered claims;
- can restrict accepted wallet product subjects by configured patterns;
- store a digest and verified claims, not the raw attestation JWT.

This profile follows the HAIP high-assurance boundary. Ecosystem-specific Wallet
Attestation claims still require ecosystem policy and interoperability testing.

### Credential policy negotiation

Organization policies can constrain:

- credential formats;
- credential types;
- required claims;
- holder-proof algorithms;
- federation/trust-framework membership;
- wallet attestation;
- hardware-backed wallet-key evidence;
- assurance level.

Negotiation produces an auditable allow/deny decision. It does not issue a credential by
itself and does not treat wallet-advertised trust-framework strings as evidence. Required
trust frameworks are evaluated against a previously validated federation entity.

## Phase 12B — HSM signing, confidential inference, workload identity and runtime response

### HSM-backed credential signing

`HsmSigningKey` stores only:

- provider;
- external key reference;
- ES256 public JWK;
- approval/activation state.

Private signing keys remain in AWS KMS/HSM or Azure HSM-backed Key Vault/Managed HSM. Credential issuance uses
the active approved external key when present. If `PHASE12_REQUIRE_HSM_SIGNING=true`,
issuance fails closed when no approved active HSM key exists.

The development encrypted local issuer key remains only as an explicitly configurable
fallback for non-production environments.

### Confidential inference

Confidential inference is fail-closed around:

- organization policy;
- allowed data categories;
- short-lived verified workload attestation;
- approved workload measurements;
- a fixed configured inference endpoint;
- HTTPS outside localhost;
- endpoint host allowlisting;
- redirect refusal.

The platform does not let users submit arbitrary inference URLs.

### SPIFFE/SPIRE service identity

Phase 12 includes deployment values and application configuration for SPIFFE/SPIRE:

- trust domain is explicit;
- Workload API socket is mounted/provided by the platform;
- workload SVID private keys are not copied into application secrets;
- workload identity policies constrain SPIFFE IDs and peers.

Production service-to-service mTLS should be enforced by a service mesh or proxy that
consumes SVIDs from the SPIFFE Workload API.

### Runtime detection and bounded containment

Runtime sensor events are authenticated with a separate sensor credential and normalized
before storage. Common secret-bearing fields are redacted.

Containment policy distinguishes reversible application actions from infrastructure actions.

Automatic reversible actions:
- disable organization provider integrations;
- pause automated career-monitor policies.

Human/authorized-controller actions:
- request network quarantine;
- request workload isolation.

Phase 12 intentionally does not give the web API broad Kubernetes-admin credentials.
Infrastructure isolation is handed to a dedicated workload-identity-protected controller.

## Production gates

1. Run official OpenID Federation and OpenID4VC conformance/interoperability tests where applicable.
2. Verify federation metadata-policy semantics required by your actual trust framework.
3. Pin and independently validate federation trust anchors.
4. Require HSM signing in production.
5. Configure cloud IAM so the API can sign with the specific HSM/KMS key but cannot export it.
6. Verify confidential-compute attestation cryptographically before recording `verified=true`.
7. Keep SPIFFE trust domains, registration entries and workload selectors under change control.
8. Deploy runtime sensors and the sensor gateway with least privilege.
9. Keep destructive infrastructure containment behind a dedicated security controller and approval policy.
10. Exercise containment/recovery in staging before enabling auto-actions.
