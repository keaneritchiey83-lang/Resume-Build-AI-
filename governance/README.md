# Phase 7 Governance

This directory contains repository-controlled governance artifacts.

- `policies/career.rego`: optional OPA policy mirror of the in-process baseline gate.
- `evals/default_cases.json`: baseline deterministic AI-safety evaluation cases.
- `control_catalog.json`: engineering evidence mapping for SOC 2 preparation.

The SOC 2 mapping is not AICPA criteria text, a SOC 2 report, an attestation, or a
certification. An independent qualified auditor determines whether controls meet
the applicable Trust Services Criteria.

Fairness monitoring accepts aggregate cohort counts only. Small cohorts are
suppressed and threshold crossings create a human-review item; they do not alter
candidate scores or produce legal conclusions.
