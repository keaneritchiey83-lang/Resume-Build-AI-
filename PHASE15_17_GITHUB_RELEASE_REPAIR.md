# Phase 15–17 — GitHub release repair

**Current status: HOLD (not production ready).**

The repository `keaneritchiey83-lang/Resume-Build-AI-` has a draft pull request #7 and a fail-closed source gate. Its GitHub Actions run **40950780689** executed and failed because the complete application was not committed. GitHub Actions reported missing `backend/pyproject.toml`, `frontend/package.json`, `ops/phase15_17/run_release_checks.py`, `.github/workflows/ci.yml`, and `.github/workflows/phase14-live-validation.yml`.

## 1. Publish the complete source safely

First extract `global-career-ai-phases15-17-release-repair.zip` beside the ZIP file. Run the commands below from that directory on a workstation with working Internet access, Git, and an authenticated GitHub account with write permission to the repository. Do **not** store an access token in the project or paste it into a command. If using GitHub CLI, authenticate with `gh auth login` and `gh auth setup-git`.

```bash
# From the directory containing this project and its release ZIP:
python global-career-ai-phase14/scripts/publish_to_github.py global-career-ai-phases15-17-release-repair.zip
# Review the validation summary and ensure the ZIP is intended for the public repository.
python global-career-ai-phase14/scripts/publish_to_github.py global-career-ai-phases15-17-release-repair.zip --push
```

The script validates ZIP checksums, confirms required application files, refuses common secret/database files, checks for private-key blocks, and stages all application files at the repository root on `release/phase15-17-ci-readiness-20261029`. It preserves the repository's old README under `docs/ORIGINAL_REPOSITORY_OVERVIEW.md`, creates a non-forced commit, and pushes only the release branch. A generic pattern scanner cannot guarantee the source contains no sensitive content: perform manual review of all files before publishing to a **public** repository. If the application includes confidential material, use a private repository instead.

This updated archive includes the importer script and this guide. Its root folder should remain `global-career-ai-phase14/` when packing; the script flattens it into the repository root.

## 2. Get actual GitHub-hosted results

Review PR #7 (`https://github.com/keaneritchiey83-lang/Resume-Build-AI-/pull/7`) and GitHub Actions on the **release** branch. All workflow results should be recorded against the same commit SHA. The imported source contains these critical workflows:

- `.github/workflows/ci.yml`: backend pytest + governance; npm install + TypeScript/Vite production build; Terraform; Kubernetes configuration.
- `.github/workflows/phase14-live-validation.yml`: disposable Docker Compose, live PostgreSQL/pgvector migration checks, authenticated integration smoke, teardown.
- `.github/workflows/phase15-17-release-readiness.yml`: non-disruptive preflight evidence artifact.

Rerun failed jobs only after reviewing the actual failed job logs. Do not mark a blocked or skipped job as PASS. A green preflight is **not** a green integrated release.

## 3. Independent security review and authorized staging failover

Use a **protected GitHub environment** named `staging`, a named approving reviewer, scoped `STAGING_KUBECONFIG_B64`, and explicit, verified staging-only endpoints. Check the Kubernetes context against the intended staging cluster before any cutover. The manually dispatched `phase14-staging-failover.yml` requires the `FAILOVER STAGING` confirmation and should run only in an approved maintenance window with a rollback plan. It is not an automatic production failover feature.

A successful local unit suite, full hosted CI, live database and Compose tests, independent security sign-off, and staging failover-and-restore evidence are required before production release is considered. **Production deployment is not authorized by this document.**
