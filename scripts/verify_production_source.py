#!/usr/bin/env python3
"""Verify the exported production source, its provenance, and Git references."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

RECORD = 'docs/baselines/current-production.json'
MANIFEST = 'docs/baselines/production-source-manifest-20261110-report.json'


def verify(root: Path) -> dict:
    root = root.resolve()
    record = json.loads((root / RECORD).read_text())
    manifest = json.loads((root / MANIFEST).read_text())
    errors = []
    original = manifest['original_source_commit']
    if record.get('source_commit') != original:
        errors.append('production record does not identify the manifest runtime commit')
    if record.get('git_source_management', {}).get('original_runtime_commit') != original:
        errors.append('Git provenance does not identify the manifest runtime commit')
    mutable = set(manifest.get('mutable_metadata', []))
    seen = set()
    checked = 0
    for item in manifest['files']:
        name = item['path']
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or name in seen:
            errors.append('invalid or duplicate manifest path: ' + name)
            continue
        seen.add(name)
        if name in mutable:
            continue
        target = root / name
        if not target.is_file() or target.is_symlink():
            errors.append('missing or non-regular source: ' + name)
            continue
        if root not in target.resolve().parents:
            errors.append('source escapes repository: ' + name)
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != item['sha256']:
            errors.append('source differs from original runtime snapshot: ' + name)
        checked += 1
    if not manifest['files']:
        errors.append('empty source manifest')
    return {'passed': not errors, 'original_runtime_commit': original,
            'checked_files': checked, 'errors': errors}


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def check_git(root: Path, *, refs: bool, clean: bool) -> list[str]:
    errors = []
    record = json.loads((root / RECORD).read_text())
    provenance = record['git_source_management']
    parent = provenance['source_snapshot_commit']
    if subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor',
                       parent, 'HEAD'], capture_output=True).returncode:
        errors.append('HEAD does not descend from the recorded clean source snapshot')
    if refs:
        try:
            branch = git(root, 'rev-parse', provenance['production_branch'] + '^{commit}')
            tag = git(root, 'rev-parse', provenance['production_tag'] + '^{commit}')
            if branch != tag:
                errors.append('production branch and release tag identify different commits')
        except subprocess.CalledProcessError:
            errors.append('production branch or release tag is missing')
    if clean and git(root, 'status', '--porcelain', '--untracked-files=all'):
        errors.append('repository has uncommitted or untracked files')
    for name in git(root, 'ls-files', '-z').split('\0'):
        if not name:
            continue
        path = PurePosixPath(name)
        if ((path.name.startswith('.env') and not path.name.endswith('.example'))
                or path.suffix in {'.pem', '.key', '.p12', '.dump', '.db', '.sqlite3'}
                or path.parts[0] in {'runtime', 'deploy_data', 'backups', 'output'}
                or any(p in {'node_modules', '.venv', '__pycache__'} for p in path.parts)):
            errors.append('private or generated file tracked by Git: ' + name)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--check-refs', action='store_true')
    parser.add_argument('--require-clean', action='store_true')
    args = parser.parse_args()
    try:
        result = verify(args.root)
        result['errors'].extend(check_git(args.root, refs=args.check_refs,
                                           clean=args.require_clean))
        result['passed'] = not result['errors']
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        result = {'passed': False, 'errors': ['verification unavailable: ' + type(exc).__name__]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
