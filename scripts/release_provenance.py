#!/usr/bin/env python3
"""Create and verify a provenance manifest for an immutable application release.

The manifest contains hashes and identifiers only. Environment values are never
written; only a hash of the non-secret environment projection is recorded.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from check_model_selection_alignment import check_alignment  # noqa: E402


REQUIRED_IMAGES = {"backend", "frontend", "worker", "md-worker", "ligand-worker"}
REPORT_SCHEMA_VERSION = "1.1"
WET_LAB_SCHEMA_VERSION = "wet_lab_plan_v1"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IMMUTABLE_REF_RE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
SECRET_NAME_RE = re.compile(r"(SECRET|PASSWORD|TOKEN|API.?KEY|PRIVATE|CREDENTIAL|ACCESS.?KEY|_URL$)", re.I)


class ManifestError(ValueError):
    pass


def _run_git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ManifestError(f"git {' '.join(args)} failed") from exc
    return result.stdout.strip()


def _dirty_paths(root: Path) -> list[str]:
    output = _run_git(root, "status", "--porcelain")
    paths = []
    for line in output.splitlines():
        if len(line) >= 4:
            paths.append(line[3:].strip().strip('"'))
    return paths


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_file(root: Path, value: str) -> tuple[Path, str]:
    candidate = Path(value)
    path = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        relative = path.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ManifestError(f"file path escapes repository root: {value}") from exc
    if not path.is_file():
        raise ManifestError(f"required release input is missing: {relative}")
    return path, relative


def _non_secret_environment_hash(root: Path, env_files: list[str]) -> str:
    projected: dict[str, str] = {}
    for name in env_files:
        path, relative = _relative_file(root, name)
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or SECRET_NAME_RE.search(key):
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            projected[key] = value
    if not env_files:
        return _sha256_bytes(b"")
    return _sha256_bytes("\n".join(f"{key}={projected[key]}" for key in sorted(projected)).encode())


def _parse_images(values: list[str]) -> dict[str, dict[str, str]]:
    images: dict[str, dict[str, str]] = {}
    for value in values:
        if "=" not in value:
            raise ManifestError("image must use SERVICE=REPOSITORY@sha256:DIGEST format")
        service, image_ref = value.split("=", 1)
        service, image_ref = service.strip(), image_ref.strip()
        if service not in REQUIRED_IMAGES:
            raise ManifestError(f"unsupported image service: {service}")
        if service in images:
            raise ManifestError(f"duplicate image service: {service}")
        if not IMMUTABLE_REF_RE.fullmatch(image_ref):
            raise ManifestError(f"{service} image must be pinned by @sha256 digest")
        digest = image_ref.rsplit("@", 1)[1]
        images[service] = {"immutable_ref": image_ref, "digest": digest}
    missing = sorted(REQUIRED_IMAGES - images.keys())
    if missing:
        raise ManifestError("missing required images: " + ", ".join(missing))
    return dict(sorted(images.items()))


def _validate_manifest(payload: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(payload, dict):
        return ["manifest root must be an object"]
    expected_top = {"manifest_version", "release_id", "created_at", "source", "compose", "images", "rollback"}
    if set(payload) not in [expected_top, expected_top | {"alignment"}]:
        failures.append("manifest fields do not match schema v1")
    if payload.get("manifest_version") != 1:
        failures.append("manifest_version must be 1")
    if not isinstance(payload.get("release_id"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", payload.get("release_id", "")):
        failures.append("release_id is invalid")
    try:
        datetime.fromisoformat(str(payload.get("created_at", "")).replace("Z", "+00:00"))
    except ValueError:
        failures.append("created_at must be an ISO-8601 timestamp")

    source = payload.get("source")
    if not isinstance(source, dict) or set(source) != {"git_commit", "git_tree", "worktree_clean"}:
        failures.append("source fields do not match schema v1")
    else:
        for name in ("git_commit", "git_tree"):
            if not isinstance(source.get(name), str) or not re.fullmatch(r"[0-9a-f]{40,64}", source[name]):
                failures.append(f"source.{name} must be a full git object id")
        if not isinstance(source.get("worktree_clean"), bool):
            failures.append("source.worktree_clean must be boolean")

    compose = payload.get("compose")
    if not isinstance(compose, dict) or set(compose) != {"files", "env_non_secret_sha256"}:
        failures.append("compose fields do not match schema v1")
    else:
        files = compose.get("files")
        if not isinstance(files, list) or not files:
            failures.append("compose.files must be a non-empty list")
        else:
            paths: set[str] = set()
            for item in files:
                if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
                    failures.append("compose file entry fields do not match schema v1")
                    continue
                if not isinstance(item.get("path"), str) or item["path"] in paths:
                    failures.append("compose file paths must be unique strings")
                else:
                    paths.add(item["path"])
                if not isinstance(item.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
                    failures.append("compose file sha256 is invalid")
        if not isinstance(compose.get("env_non_secret_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", compose["env_non_secret_sha256"]):
            failures.append("compose.env_non_secret_sha256 is invalid")

    images = payload.get("images")
    if not isinstance(images, dict) or set(images) != REQUIRED_IMAGES:
        failures.append("images must contain backend, frontend, worker, md-worker, ligand-worker")
    else:
        for service, image in images.items():
            if not isinstance(image, dict) or set(image) != {"immutable_ref", "digest"}:
                failures.append(f"images.{service} fields do not match schema v1")
                continue
            if not isinstance(image.get("immutable_ref"), str) or not IMMUTABLE_REF_RE.fullmatch(image["immutable_ref"]):
                failures.append(f"images.{service}.immutable_ref must be digest pinned")
            if not isinstance(image.get("digest"), str) or not DIGEST_RE.fullmatch(image["digest"]):
                failures.append(f"images.{service}.digest is invalid")
            elif isinstance(image.get("immutable_ref"), str) and not image["immutable_ref"].endswith("@" + image["digest"]):
                failures.append(f"images.{service} reference/digest mismatch")

    rollback = payload.get("rollback")
    if rollback is not None:
        if not isinstance(rollback, dict) or set(rollback) != {"target_release_id", "manifest_sha256"}:
            failures.append("rollback fields do not match schema v1")
        elif (
            not isinstance(rollback.get("target_release_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", rollback["target_release_id"])
            or not isinstance(rollback.get("manifest_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", rollback["manifest_sha256"])
        ):
            failures.append("rollback target or manifest hash is invalid")
    alignment = payload.get("alignment")
    if alignment is not None:
        if not isinstance(alignment, dict) or set(alignment) != {
            "report_schema_version", "wet_lab_schema_version", "frontend_bundle_sha256"
        }:
            failures.append("alignment fields do not match schema v1")
        else:
            if alignment.get("report_schema_version") != REPORT_SCHEMA_VERSION:
                failures.append("alignment.report_schema_version is unsupported")
            if alignment.get("wet_lab_schema_version") != WET_LAB_SCHEMA_VERSION:
                failures.append("alignment.wet_lab_schema_version is unsupported")
            if not isinstance(alignment.get("frontend_bundle_sha256"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", alignment["frontend_bundle_sha256"]
            ):
                failures.append("alignment.frontend_bundle_sha256 is invalid")
    return failures


def build_manifest(
    *, root: Path, release_id: str, images: list[str], compose_files: list[str], env_files: list[str],
    rollback_manifest: str | None = None, rollback_release_id: str | None = None, allow_dirty: bool = False,
    frontend_bundle: str | None = None,
) -> dict[str, Any]:
    commit = _run_git(root, "rev-parse", "HEAD")
    tree = _run_git(root, "rev-parse", "HEAD^{tree}")
    dirty = bool(_run_git(root, "status", "--porcelain"))
    if dirty and not allow_dirty:
        raise ManifestError("worktree is dirty; release manifest creation requires a clean checkout")
    if bool(rollback_manifest) != bool(rollback_release_id):
        raise ManifestError("rollback manifest and rollback release id must be provided together")
    compose_entries = []
    for name in compose_files:
        path, relative = _relative_file(root, name)
        compose_entries.append({"path": relative, "sha256": _sha256_file(path)})
    if not compose_entries:
        raise ManifestError("at least one --compose-file is required")
    rollback = None
    if rollback_manifest:
        path = Path(rollback_manifest).resolve()
        if not path.is_file():
            raise ManifestError("rollback manifest does not exist")
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ManifestError("rollback manifest is not valid JSON") from exc
        previous_errors = _validate_manifest(previous)
        if previous_errors:
            raise ManifestError("rollback manifest is invalid: " + "; ".join(previous_errors))
        if previous["release_id"] != rollback_release_id:
            raise ManifestError("rollback release id does not match rollback manifest")
        rollback = {"target_release_id": rollback_release_id, "manifest_sha256": _sha256_file(path)}

    alignment = None
    if frontend_bundle is not None:
        candidate_bundle = Path(frontend_bundle)
        bundle_path = candidate_bundle.resolve() if candidate_bundle.is_absolute() else (root / candidate_bundle).resolve()
        try:
            bundle_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ManifestError(f"frontend bundle path escapes repository root: {frontend_bundle}") from exc
        if not bundle_path.exists():
            raise ManifestError(f"required frontend bundle is missing: {frontend_bundle}")
        if bundle_path.is_dir():
            bundle_digest = hashlib.sha256()
            for item in sorted(bundle_path.rglob("*")):
                if item.is_file():
                    bundle_digest.update(item.relative_to(bundle_path).as_posix().encode())
                    bundle_digest.update(item.read_bytes())
            frontend_bundle_sha256 = bundle_digest.hexdigest()
        else:
            frontend_bundle_sha256 = _sha256_file(bundle_path)
        alignment = {
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "wet_lab_schema_version": WET_LAB_SCHEMA_VERSION,
            "frontend_bundle_sha256": frontend_bundle_sha256,
        }

    payload = {
        "manifest_version": 1,
        "release_id": release_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": {"git_commit": commit, "git_tree": tree, "worktree_clean": not dirty},
        "compose": {
            "files": sorted(compose_entries, key=lambda item: item["path"]),
            "env_non_secret_sha256": _non_secret_environment_hash(root, env_files),
        },
        "images": _parse_images(images),
        "rollback": rollback,
    }
    if alignment is not None:
        payload["alignment"] = alignment
    errors = _validate_manifest(payload)
    if errors:
        raise ManifestError("generated manifest is invalid: " + "; ".join(errors))
    return payload


def verify_manifest(
    *, root: Path, manifest_path: Path, images: list[str] | None = None, env_files: list[str] | None = None,
    offline: bool = False, expected_release_id: str | None = None, required_compose_file: str | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "blocked", "failures": ["manifest cannot be read as JSON"]}
    failures.extend(_validate_manifest(payload))
    if failures:
        return {"status": "blocked", "failures": failures}

    if expected_release_id is not None and payload["release_id"] != expected_release_id:
        failures.append("release id differs from manifest")
    if required_compose_file is not None:
        required_path = Path(required_compose_file)
        try:
            required_relative = required_path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            required_relative = required_path.as_posix()
        manifest_paths = {item["path"] for item in payload["compose"]["files"]}
        if required_relative not in manifest_paths:
            failures.append(f"compose file is not bound by manifest: {required_relative}")

    commit = None
    if not offline:
        try:
            commit = _run_git(root, "rev-parse", "HEAD")
            tree = _run_git(root, "rev-parse", "HEAD^{tree}")
            dirty_paths = _dirty_paths(root)
        except ManifestError as exc:
            return {"status": "blocked", "failures": [str(exc)]}
        if payload["source"]["git_commit"] != commit:
            failures.append("git commit differs from manifest")
        if payload["source"]["git_tree"] != tree:
            failures.append("git tree differs from manifest")
        manifest_relative = None
        try:
            manifest_relative = manifest_path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
        unexpected_dirty = [path for path in dirty_paths if path != manifest_relative]
        if unexpected_dirty or not payload["source"]["worktree_clean"]:
            failures.append("worktree is not clean")
    elif not payload["source"]["worktree_clean"]:
        failures.append("manifest source is marked dirty")
    model_failures = check_alignment(root)
    if model_failures:
        failures.append("model selection mismatch: " + ", ".join(model_failures))

    for item in payload["compose"]["files"]:
        try:
            path, _ = _relative_file(root, item["path"])
            if _sha256_file(path) != item["sha256"]:
                failures.append(f"compose source hash mismatch: {item['path']}")
        except ManifestError as exc:
            failures.append(str(exc))
    if env_files is not None:
        try:
            if _non_secret_environment_hash(root, env_files) != payload["compose"]["env_non_secret_sha256"]:
                failures.append("non-secret environment fingerprint mismatch")
        except ManifestError as exc:
            failures.append(str(exc))
    if images is not None:
        try:
            if _parse_images(images) != payload["images"]:
                failures.append("image digest set differs from manifest")
        except ManifestError as exc:
            failures.append(str(exc))
    return {
        "status": "blocked" if failures else "verified",
        "release_id": payload["release_id"],
        "git_commit": commit,
        "image_services": sorted(payload["images"]),
        "failures": failures,
    }


def compose_environment(payload: dict[str, Any]) -> dict[str, str]:
    """Map manifest image entries to Compose interpolation variables."""
    errors = _validate_manifest(payload)
    if errors:
        raise ManifestError("manifest is invalid: " + "; ".join(errors))
    images = payload["images"]
    return {
        "RELEASE_ID": payload["release_id"],
        "BACKEND_IMAGE": images["backend"]["immutable_ref"],
        "FRONTEND_IMAGE": images["frontend"]["immutable_ref"],
        "WORKER_IMAGE": images["worker"]["immutable_ref"],
        "MD_WORKER_IMAGE": images["md-worker"]["immutable_ref"],
        "LIGAND_WORKER_IMAGE": images["ligand-worker"]["immutable_ref"],
    }


def _key_value(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected NAME=VALUE")
    return tuple(value.split("=", 1))  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="create a release manifest after immutable images are built")
    create.add_argument("--release-id", required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--image", action="append", default=[], metavar="SERVICE=REPOSITORY@sha256:DIGEST", required=True)
    create.add_argument("--compose-file", action="append", default=[], required=True)
    create.add_argument("--env-file", action="append", default=[])
    create.add_argument("--rollback-manifest")
    create.add_argument("--rollback-release-id")
    create.add_argument("--frontend-bundle", default="frontend/dist", help="Built frontend directory or bundle file to hash")
    create.add_argument("--allow-dirty", action="store_true", help="write an explicitly non-deployable audit manifest")

    verify = subparsers.add_parser("verify", help="verify source, compose, environment fingerprint, and optional image digests")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--image", action="append", default=[], metavar="SERVICE=REPOSITORY@sha256:DIGEST")
    verify.add_argument("--env-file", action="append")
    verify.add_argument("--offline", action="store_true", help="verify an extracted release without a .git checkout")
    verify.add_argument("--expected-release-id")
    verify.add_argument("--require-compose-file")

    render = subparsers.add_parser("compose-env", help="render digest-pinned Compose interpolation variables")
    render.add_argument("--manifest", type=Path, required=True)
    render.add_argument("--format", choices=("shell", "json"), default="shell")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "create":
            payload = build_manifest(
                root=root, release_id=args.release_id, images=args.image, compose_files=args.compose_file,
                env_files=args.env_file, rollback_manifest=args.rollback_manifest,
                rollback_release_id=args.rollback_release_id, allow_dirty=args.allow_dirty,
                frontend_bundle=args.frontend_bundle,
            )
            output = args.output if args.output.is_absolute() else root / args.output
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"status": "created", "release_id": payload["release_id"], "output": str(output)}, ensure_ascii=False))
            return 0
        manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
        if args.command == "compose-env":
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                values = compose_environment(payload)
            except (OSError, json.JSONDecodeError, ManifestError) as exc:
                raise ManifestError(str(exc)) from exc
            if args.format == "json":
                print(json.dumps(values, ensure_ascii=False, sort_keys=True))
            else:
                for key, value in values.items():
                    print(f"{key}={value}")
            return 0
        result = verify_manifest(
            root=root, manifest_path=manifest_path, images=args.image or None, env_files=args.env_file,
            offline=args.offline, expected_release_id=args.expected_release_id,
            required_compose_file=args.require_compose_file,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "verified" else 1
    except ManifestError as exc:
        print(json.dumps({"status": "blocked", "failures": [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
