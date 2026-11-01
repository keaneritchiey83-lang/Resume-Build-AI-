# Phase 13 governance artifacts

These files document implementation controls; they are not certifications.

- `trust_continuity_profile.json` covers multi-region trust continuity.
- `ai_security_profile.json` covers the Phase 13 model/agent security gateway.
- `../policies/career.rego` contains enforceable OPA policy rules.

The prompt-injection score is deliberately not treated as a complete defense.
Privileged action capability is isolated from the model and must pass an
independent permission-manifest decision.
