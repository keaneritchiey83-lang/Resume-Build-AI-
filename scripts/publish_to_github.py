#!/usr/bin/env python3
"""Safely stage or publish the complete Phase 15–17 ZIP to a GitHub release branch.

This script requires a connected machine with git and GitHub write credentials.
It never changes main, deploys services, uses secrets, or runs failover.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote
import zipfile

REQUIRED = (
    'backend/pyproject.toml',
    'frontend/package.json',
    'ops/phase15_17/run_release_checks.py',
    '.github/workflows/ci.yml',
    '.github/workflows/phase14-live-validation.yml',
    '.github/workflows/phase15-17-release-readiness.yml',
)
BANNED_FILE_SUFFIXES = ('.pem', '.p12', '.pfx', '.jks', '.key', '.sqlite', '.sqlite3', '.db', '.log')
BANNED_SEGMENTS = {'node_modules', '__pycache__', '.git', '.venv', '.pytest_cache', '.terraform'}
BANNED_NAMES = {'.env', '.npmrc', '.pypirc', 'id_rsa', 'id_ed25519', 'credentials.json', 'service-account.json'}
ZIP_ROOT = 'global-career-ai-phase14/'
KEY_MARKER = re.compile(rb'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----')
REPO_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$')


def checked_entries(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    """Fail closed on unsafe paths, symlinks, sensitive files, duplicate paths."""
    result: list[tuple[zipfile.ZipInfo, str]] = []
    paths: set[str] = set()
    for info in archive.infolist():
        if info.is_dir():
            continue
        if not info.filename.startswith(ZIP_ROOT):
            raise ValueError(f'Unexpected ZIP root: {info.filename}')
        path = PurePosixPath(info.filename[len(ZIP_ROOT):])
        parts = path.parts
        if (not parts or path.is_absolute() or any(x in ('', '.', '..') for x in parts)
                or '\\' in info.filename or ':' in info.filename):
            raise ValueError(f'Unsafe ZIP entry: {info.filename}')
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError(f'Symbolic links not allowed: {info.filename}')
        if set(parts) & BANNED_SEGMENTS or path.name in BANNED_NAMES:
            raise ValueError(f'Sensitive/generated path not allowed: {path}')
        if path.name.startswith('.env.') and path.name != '.env.example':
            raise ValueError(f'Environment configuration not allowed: {path}')
        if path.suffix.lower() in BANNED_FILE_SUFFIXES:
            raise ValueError(f'Potential secret/database file not allowed: {path}')
        if info.file_size > 15_000_000:
            raise ValueError(f'Oversized ZIP entry: {path}')
        if str(path) in paths:
            raise ValueError(f'Duplicate ZIP entry: {path}')
        raw = archive.read(info)
        if KEY_MARKER.search(raw):
            raise ValueError(f'Private-key material detected: {path}')
        paths.add(str(path))
        result.append((info, str(path)))
    missing = set(REQUIRED) - paths
    if missing:
        raise ValueError(f'ZIP missing required files: {sorted(missing)}')
    return result


def git(*args: str, cwd: Path | None = None) -> str:
    cmd = ['git', *args]
    result = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(f'{" ".join(cmd[:4])} failed: {result.stderr.strip()[-900:]}')
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip_file', type=Path)
    parser.add_argument('--repo', default='keaneritchiey83-lang/Resume-Build-AI-')
    parser.add_argument('--branch', default='release/phase15-17-ci-readiness-20261029')
    parser.add_argument('--push', action='store_true', help='Explicitly publish a commit to GitHub')
    parser.add_argument('--retain', action='store_true', help='Keep a temp checkout for manual inspection')
    args = parser.parse_args(argv)
    if not REPO_PATTERN.fullmatch(args.repo):
        parser.error('--repo must use owner/repository')
    if args.branch in ('main', 'master') or not args.branch.startswith('release/'):
        parser.error('--branch must be a non-default release/... branch')
    if shutil.which('git') is None:
        parser.error('git is required')
    if not args.zip_file.is_file():
        parser.error(f'ZIP not found: {args.zip_file}')

    with zipfile.ZipFile(args.zip_file) as archive:
        if archive.testzip():
            raise ValueError('ZIP checksum validation failed')
        entries = checked_entries(archive)
        print(f'PASS: validated {len(entries)} source files; no prohibited paths or private-key blocks')
        if not args.push:
            print('DRY RUN: no GitHub changes made. Pass --push to create and push the release commit.')
            return 0
        # Git will validate commit author identity on the connected workstation.

        checkout = Path(tempfile.mkdtemp(prefix='gcai-github-release-'))
        try:
            # GitHub authentication is delegated to the user's existing git/gh credential setup.
            git('clone', '--quiet', f'https://github.com/{quote(args.repo, safe="/")}.git', str(checkout))
            remote_branches = git('branch', '-r', cwd=checkout)
            if f'origin/{args.branch}' in [line.strip() for line in remote_branches.splitlines()]:
                git('switch', '--track', '-c', args.branch, f'origin/{args.branch}', cwd=checkout)
            else:
                git('switch', '-c', args.branch, cwd=checkout)

            overview = checkout / 'README.md'
            backup = checkout / 'docs' / 'ORIGINAL_REPOSITORY_OVERVIEW.md'
            if overview.exists() and not backup.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(overview.read_bytes())

            for info, rel in entries:
                target = checkout.joinpath(*PurePosixPath(rel).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
            git('add', '--all', cwd=checkout)
            changed = git('diff', '--cached', '--name-only', cwd=checkout).splitlines()
            print(f'STAGED: {len(changed)} changes on {args.branch}')
            if not changed:
                print('No changes; repository release branch already matches archive.')
                return 0
            git('commit', '-m', 'feat: import complete Phase 15–17 B-track application', cwd=checkout)
            # Non-forced update; protection/branch conflicts fail visibly.
            git('push', '--set-upstream', 'origin', args.branch, cwd=checkout)
            print(f'PUBLISHED: https://github.com/{args.repo}/tree/{args.branch}')
            print('Next: inspect GitHub Actions CI and staging checks before merging.')
        finally:
            if args.retain:
                print(f'RETAINED CHECKOUT: {checkout}')
            else:
                shutil.rmtree(checkout, ignore_errors=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, zipfile.BadZipFile) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
