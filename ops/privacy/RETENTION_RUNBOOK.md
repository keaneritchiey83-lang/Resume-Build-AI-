# Retention and Legal-Hold Runbook

Retention policies operate only on an allowlisted set of record types. They never construct
arbitrary table names or SQL from user input.

Before enabling a policy:

1. map the data asset in the lineage registry;
2. document processing purpose and retention basis;
3. review contractual, employment, litigation and regulatory preservation duties;
4. set `legal_hold=true` whenever deletion must pause;
5. test the policy in non-production with representative records;
6. monitor the deletion count and audit event.

A legal hold always blocks the Phase-9 automated deletion path.
