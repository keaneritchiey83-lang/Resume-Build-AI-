# Phase 13 AI security runbook

## Model gateway

- Pin organization-approved models.
- Prefer immutable model snapshots when the provider exposes them.
- Require a passed evaluation run before a production model release.
- Sign the release manifest and record its digest in the transparency chain.
- Keep tools disabled in the model gateway.
- Keep job-board/provider credentials outside model context.

## Prompt injection

Treat all job descriptions, retrieved career articles, webhook content, emails, and external
documents as untrusted data.

The detection score is a triage signal only. A successful prompt injection should still be
unable to cause a privileged action because:
- the gateway exposes no action tools;
- retrieved content is placed in a clearly delimited untrusted section;
- agent actions require a separate permission-manifest decision;
- destinations and data categories are allowlisted;
- selected actions require human approval.

## Confidential RAG

- Retrieve only approved knowledge records.
- Exclude content that crosses the block threshold.
- Record content digests rather than duplicating plaintext into audit tables.
- Do not retrieve candidate secrets, API credentials, or hidden system prompts.
- Use confidential-inference policies from Phase 12 for sensitive workloads.

## Incident response

1. Disable the affected model release or agent manifest.
2. Preserve the prompt-injection event and RAG document digests.
3. Pause automatic career agents when necessary.
4. Open a human-review/security incident.
5. Re-run red-team and governance evaluation suites before reactivation.
