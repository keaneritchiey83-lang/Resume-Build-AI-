# AI Incident Runbook — Phase 8

## Purpose

Handle suspected AI incidents without allowing an automated severity label to become a legal
conclusion. The `serious_incident_candidate` field is a triage flag only.

## Workflow

1. Preserve relevant logs, model/version IDs, policy/eval results, prompts/outputs where retention
   is lawful, and deployment configuration.
2. Contain the behavior: disable affected route/model/workflow or narrow its allowed actions.
3. Protect candidate data and avoid copying sensitive personal data into tickets or chat systems.
4. Assign an incident commander plus privacy/security/AI-governance owners.
5. Determine affected people, jurisdictions, use cases, duration, and whether employment decisions
   were materially influenced.
6. Perform legal/regulatory reporting analysis using current law and the actual facts. Do not infer
   a reporting deadline solely from the application severity.
7. Correct the issue, add regression evaluations/policy checks, and require human approval before
   restoring high-impact workflows.
8. Record post-incident findings and update the AI inventory, risk assessment, controls, training,
   and evidence catalog.

## Minimum evidence

- AI inventory ID and version
- model/workflow versions
- detection time and containment time
- impact description
- human decisions/overrides
- relevant evaluations and logs
- corrective actions
- reporting decision and rationale
- closure approval

## EU AI Act note

Employment-related AI may fall within Annex III. The application records a conservative
classification candidate and the current applicability date, but counsel/compliance must determine
actual status, operator obligations, serious-incident treatment, and reporting requirements.
