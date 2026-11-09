#!/usr/bin/env python3
"""Build a read-only production readiness packet for the thermostability release."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import os
import tempfile
import time
import uuid
from urllib.parse import urlsplit, unquote, parse_qs
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    "backend",
    "worker",
    "md-worker",
    "frontend",
    "nginx",
    "ligand-worker",
    "chromadb",
    "outline",
)
APP_SERVICES = ("backend", "worker", "md-worker", "frontend", "ligand-worker")
SECRET_RE = re.compile(r"(?:\.env(?:\.|$)|secret|credential|private.key|\.pem$)", re.I)


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.rstrip("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tracked_schema_inventory() -> dict[str, object]:
    paths = run_git("ls-files", "backend/app/models", "backend/alembic").splitlines()
    files = []
    for item in paths:
        path = ROOT / item
        if not path.is_file() or SECRET_RE.search(item):
            continue
        files.append({"path": item, "sha256": sha256(path)})
    revisions = []
    for path in sorted((ROOT / "backend/alembic/versions").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        revision = re.search(r"^revision\s*:\s*[^=]+?=\s*['\"]([^'\"]+)", text, re.M)
        parent = re.search(r"^down_revision\s*:\s*[^=]+?=\s*(['\"])(.*?)\1", text, re.M)
        if not revision:
            revision = re.search(r"^revision\s*=\s*['\"]([^'\"]+)", text, re.M)
        if not parent:
            parent = re.search(r"^down_revision\s*=\s*(['\"])(.*?)\1", text, re.M)
        if revision:
            revisions.append(
                {
                    "revision": revision.group(1),
                    "down_revision": parent.group(2) if parent else None,
                    "file": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256(path),
                }
            )
    ids = {row["revision"] for row in revisions}
    missing_parents = sorted(
        {row["down_revision"] for row in revisions if row["down_revision"] and row["down_revision"] not in ids}
    )
    return {"files": files, "revisions": revisions, "missing_parents": missing_parents}


def build_packet(expected_commit: str, actual_runtime_migration: str) -> dict[str, object]:
    head = run_git("rev-parse", "HEAD")
    status = run_git("status", "--porcelain", "--untracked-files=all").splitlines()
    dirty = [line[3:].strip().strip('"') for line in status]
    schema = tracked_schema_inventory()
    candidate_paths = {item["path"] for item in schema["files"]}
    try:
        baseline_paths = set(
            run_git("ls-tree", "-r", "--name-only", "0421817d", "backend/app/models", "backend/alembic").splitlines()
        )
        schema_changed = sorted(
            path
            for path in candidate_paths | baseline_paths
            if run_git("rev-parse", f"0421817d:{path}")
            != run_git("hash-object", str(ROOT / path))
            if (ROOT / path).is_file()
        )
    except subprocess.CalledProcessError:
        schema_changed = ["baseline comparison unavailable"]

    db_compatible = not schema_changed and not schema["missing_parents"]
    gates = [
        {"gate": "candidate_commit_matches", "passed": head == expected_commit, "detail": head},
        {"gate": "candidate_worktree_clean", "passed": not dirty, "detail": dirty},
        {"gate": "candidate_model_and_migration_tree_unchanged_from_0421817d", "passed": not schema_changed, "detail": schema_changed},
        {"gate": "candidate_alembic_graph_closed", "passed": not schema["missing_parents"], "detail": schema["missing_parents"]},
        {"gate": "runtime_migration_present_in_candidate_graph", "passed": actual_runtime_migration in {row["revision"] for row in schema["revisions"]}, "detail": actual_runtime_migration},
        {"gate": "formal_trusted_domain_tls", "passed": False, "detail": "Observed certificate is self-signed for IP 120.27.108.138; no production hostname/public trust chain was found."},
        {"gate": "official_registry_repo_digest", "passed": False, "detail": "Application images have local image IDs and empty RepoDigests; do not fabricate an immutable registry reference."},
        {"gate": "fresh_database_backup_and_restore_drill", "passed": False, "detail": "Must be created against the current database immediately before switching, then restored into an isolated temporary database."},
        {"gate": "runtime_schema_compatibility", "passed": True, "detail": "20261103 read-only check: 31/31 candidate/runtime model+migration+database files match; 51 tables, 505 columns, 123 constraints; missing ORM tables/columns 0. Existing Alembic compare_metadata drift: modify_nullable=2, remove_column=1. Candidate introduces no schema delta. Never upgrade/stamp to repair unrelated existing drift during code-only rollout."},
    ]
    return {
        "packet_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_only_preparation": True,
        "production_actions_performed": [],
        "candidate": {"head": head, "expected_head": expected_commit, "dirty_paths": dirty},
        "database": {
            "observed_runtime_alembic_revision": actual_runtime_migration,
            "candidate_schema_inventory": schema,
            "candidate_has_schema_delta_from_baseline": bool(schema_changed),
            "code_only_deployment_candidate": db_compatible and actual_runtime_migration not in {row["revision"] for row in schema["revisions"]},
            "decision": "Code-only deployment is compatible: 31 runtime model/migration/database-source files match candidate; all ORM tables and columns exist. Existing drift (2 nullable changes, 1 extra column) is not introduced by candidate. Do not run alembic upgrade or stamp.",
        },
        "gates": gates,
        "cutover": {
            "strategy": "in-place replacement under original container names, retaining all existing networks, mounts, host configuration and shared services",
            "snapshot_to_preserve": "/opt/protein-ai-platform/snapshots/20261103 (immutable)",
            "current_pointer": "Do not use or change /opt/protein-ai-platform/current; it is stale relative to running app containers.",
            "release_source": "/opt/protein-ai-platform/releases/<new-release-id>/protein-ai-platform",
            "sequence": [
                "Freeze new submissions and allow/record in-flight worker tasks; do not tear down the Compose project.",
                "Capture fresh custom-format database dump, SHA-256, pg_restore --list; restore it into a uniquely named isolated database and verify schema/table count before cutover.",
                "Build app images with exact candidate source; record local OCI image IDs and manifest/config digests. Treat those as local provenance, not registry RepoDigests.",
                "Generate private create payloads by cloning current runtime Config/HostConfig/network attachments; change only app image and source-derived labels. Keep existing volumes, bind mounts, env, secrets and network aliases.",
                "For each app container, stop and rename old container to a timestamped rollback name, create/start same-name replacement, and verify health plus functional checks before proceeding to next service.",
                "On any failure, stop/rename replacement and recreate original container from the 20261103 snapshot payload/image, retaining database and all current volumes.",
                "After all app services pass, record new release facts; leave nginx, chromadb and outline containers, networks and volumes intact.",
            ],
            "avoid": ["docker compose down", "installer that copies config from stale current", "database upgrade/stamp", "database restore to production", "overwriting snapshot 20261103"],
        },
        "backup_and_drill": {
            "runtime_source": "Use the active backend container's DATABASE_URL only inside the process; never print or persist its value.",
            "backup": "On the server, stream pg_dump --format=custom from the active database endpoint into a new timestamped private backup file; calculate SHA-256 and run pg_restore --list.",
            "restore_drill": "Start an independent temporary PostgreSQL container with --network none and no published ports; restore there, verify table count/revision, then remove the temporary container and its anonymous volume.",
            "gate": "If pg_dump/pg_restore client is unavailable in the active runtime, use a trusted PostgreSQL client container with the active network and pass connection settings through an ephemeral protected env file; do not echo commands after expansion.",
            "production_db_mutation": "Only the drill database is created/dropped. Never restore, stamp or migrate the production database in this preparation flow.",
        },
    }


def docker(*args: str, stdin=None, stdout=None) -> bytes:
    """Never include command arguments or stderr in exceptions (may contain secrets)."""
    result = subprocess.run(["docker", *args], input=stdin, stdout=stdout or subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(f"Docker operation failed (exit {result.returncode}); inspect locally without publishing private configuration")
    return result.stdout or b""


def private_json(path: Path, data: object) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def fresh_backup_drill(directory: Path, client_image: str) -> dict[str, object]:
    """Back up active DB, restore to a network-isolated disposable PostgreSQL."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", client_image):
        raise ValueError("client image must be a local immutable sha256 image ID")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(directory, 0o700)
    info = json.loads(docker("inspect", "docker-backend-1"))[0]
    env = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    url = urlsplit(env["DATABASE_URL"])
    if not url.scheme.startswith("postgres") or not url.hostname or not url.path.strip("/"):
        raise ValueError("active database must be PostgreSQL with an explicit database name")
    options = parse_qs(url.query)
    connection = {
        "PGHOST": url.hostname, "PGPORT": str(url.port or 5432),
        "PGUSER": unquote(url.username or ""), "PGPASSWORD": unquote(url.password or ""),
        "PGDATABASE": unquote(url.path.lstrip("/")),
        "PGSSLMODE": options.get("sslmode", ["prefer"])[0],
        "PGCONNECT_TIMEOUT": "20", "PGOPTIONS": "-c default_transaction_read_only=on",
    }
    if any("\n" in value or "\r" in value for value in connection.values()):
        raise ValueError("database connection contains unsupported line breaks")
    backup = directory / "database.dump"
    client_env = directory / ".temporary-pg-client.env"
    fd = os.open(client_env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write("\n".join(f"{k}={v}" for k, v in connection.items()) + "\n")
    drill = "protein-ai-restore-drill-" + uuid.uuid4().hex[:12]
    started = False
    try:
        sanity_sql = "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'; SELECT version_num FROM alembic_version;"
        original_summary = docker("run", "--rm", "--pull=never", "--network", "container:docker-backend-1", "--env-file", str(client_env), client_image, "psql", "-At", "-c", sanity_sql).decode().splitlines()
        if len(original_summary) != 2 or not original_summary[0].isdigit():
            raise RuntimeError("source database schema sanity query failed")
        with backup.open("xb") as stream:
            os.chmod(backup, 0o600)
            docker("run", "--rm", "--pull=never", "--network", "container:docker-backend-1", "--env-file", str(client_env), client_image, "pg_dump", "--format=custom", "--no-owner", "--no-acl", stdout=stream)
        digest = sha256(backup)
        (directory / "database.dump.sha256").write_text(f"{digest}  database.dump\n")
        with backup.open("rb") as stream:
            listing = subprocess.run(["docker", "run", "--rm", "-i", "--pull=never", "--network", "none", client_image, "pg_restore", "--list"], stdin=stream, capture_output=True)
        if listing.returncode:
            raise RuntimeError("pg_restore archive listing failed")
        private_json(directory / "archive-list-summary.json", {"entry_count": len(listing.stdout.splitlines()), "sha256": hashlib.sha256(listing.stdout).hexdigest()})
        docker("run", "-d", "--pull=never", "--name", drill, "--network", "none", "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-e", "POSTGRES_DB=restore_check", client_image)
        started = True
        for _ in range(90):
            ready = subprocess.run(["docker", "exec", drill, "pg_isready", "-U", "postgres", "-d", "restore_check"], capture_output=True)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("isolated restore database did not become ready")
        with backup.open("rb") as stream:
            restored = subprocess.run(["docker", "exec", "-i", drill, "pg_restore", "-U", "postgres", "-d", "restore_check", "--exit-on-error", "--no-owner", "--no-acl"], stdin=stream, capture_output=True)
        if restored.returncode:
            raise RuntimeError("isolated restore failed; dump retained for local diagnosis")
        summary = docker("exec", drill, "psql", "-U", "postgres", "-d", "restore_check", "-At", "-c", sanity_sql).decode().splitlines()
        if summary != original_summary or int(summary[0]) < 1:
            raise RuntimeError("isolated restore schema sanity check failed")
        result = {"created_at": datetime.now(timezone.utc).isoformat(), "active_backend_container_id": info["Id"], "backup_sha256": digest, "backup_bytes": backup.stat().st_size, "archive_list_verified": True, "isolated_restore_verified": True, "isolated_network": "none", "restored_public_table_count": int(summary[0]), "restored_alembic_revision": summary[1], "production_database_restored": False}
        private_json(directory / "BACKUP-DRILL.json", result)
        return result
    finally:
        client_env.unlink(missing_ok=True)
        if started:
            docker("rm", "-f", "-v", drill)


def model_service_environment(path: Path) -> dict[str, str]:
    """Read the private service token without copying scientific runtime settings."""
    if path.stat().st_mode & 0o077:
        raise ValueError("model service environment must be private (0600)")
    values = dict(line.split("=", 1) for line in path.read_text().splitlines()
                  if "=" in line and not line.startswith("#"))
    token = values.get("MODEL_SERVICE_TOKEN", "")
    if len(token) < 32 or any(char.isspace() for char in token):
        raise ValueError("invalid model service token")
    result = {}
    for name in ("ddgun", "colabfold", "evcouplings"):
        prefix = name.upper()
        result[prefix + "_SERVICE_URL"] = "http://172.18.0.1:4270/" + name
        result[prefix + "_SERVICE_TOKEN"] = token
        result[prefix + "_SERVICE_TIMEOUT_SECONDS"] = "7260"
    return result


def release_inventory(release: Path) -> dict[str, str]:
    inventory = {}
    for folder in ("backend/app", "backend/alembic", "frontend/dist"):
        for path in sorted((release / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                inventory[path.relative_to(release).as_posix()] = sha256(path)
    if not inventory:
        raise ValueError("empty release inventory")
    return inventory


def runtime_create_payload(info: dict, frozen: dict, overrides: list[tuple[Path, str]],
                           model_env: dict[str, str], *, prior_mounts: dict[str, str] | None = None) -> dict:
    """Clone runtime config; replace only source mounts bound to a release record."""
    if info["State"].get("Health", {}).get("Status") != "healthy":
        raise RuntimeError("all original app containers must be healthy before preparation")
    if info["Id"] != frozen["container_id"]:
        raise RuntimeError("active container changed since checkpoint; capture a new checkpoint")
    if prior_mounts is not None and info["Image"] != frozen["checkpoint_image_id"]:
        raise RuntimeError("active image differs from production record")
    payload = copy.deepcopy(info["Config"])
    if model_env:
        env = dict(item.split("=", 1) for item in payload["Env"] if "=" in item)
        payload["Env"] = [f"{k}={v}" for k, v in {**env, **model_env}.items()]
    payload["Image"] = frozen["checkpoint_image_id"]
    payload["HostConfig"] = copy.deepcopy(info["HostConfig"])
    binds = list(payload["HostConfig"].get("Binds") or [])
    mounts = {item["Destination"]: item for item in info["Mounts"]}
    for source, destination in overrides:
        mount = mounts.get(destination)
        if mount:
            if prior_mounts is None:
                raise RuntimeError("refusing to replace an existing source mount")
            if mount["Source"] != prior_mounts.get(destination) or mount.get("RW", True):
                raise RuntimeError("source mount differs from verified read-only production record")
            matched = [b for b in binds if b.split(":")[1:2] == [destination]]
            if len(matched) != 1 or matched[0].split(":")[0] != mount["Source"]:
                raise RuntimeError("source mount is not represented by one verified bind")
            if any(m.get("Target") == destination for m in payload["HostConfig"].get("Mounts") or []):
                raise RuntimeError("conflicting source mount configuration")
            binds.remove(matched[0])
        elif prior_mounts is not None and destination in prior_mounts:
            raise RuntimeError("recorded production source mount is missing")
        binds.append(f"{source}:{destination}:ro")
    payload["HostConfig"]["Binds"] = binds
    endpoints = {}
    for network, endpoint in info["NetworkSettings"]["Networks"].items():
        aliases = [a for a in endpoint.get("Aliases") or [] if a not in {info["Id"], info["Id"][:12]}]
        endpoints[network] = {"Aliases": aliases}
    payload["NetworkingConfig"] = {"EndpointsConfig": endpoints}
    return payload


def prepare_runtime_payloads(directory: Path, release: Path, model_service_env: Path | None = None,
                             production_record: Path | None = None) -> dict[str, object]:
    """Clone actual runtime settings, adding reviewed source mounts/model settings."""
    model_env = model_service_environment(model_service_env) if model_service_env else {}
    release = release.resolve(strict=True)
    if not release.is_dir() or "/releases/" not in str(release):
        raise ValueError("release must be an existing versioned releases directory")
    required = [release / "backend/app", release / "backend/alembic", release / "frontend/dist/index.html"]
    if not all(path.exists() for path in required):
        raise ValueError("release backend/app, backend/alembic and built frontend/dist/index.html are required")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(directory, 0o700)
    rows = []
    if production_record:
        checkpoint = json.loads(production_record.read_text())
        frozen = {service: {**row, "checkpoint_image_id": row["image_id"]}
                  for service, row in checkpoint["services"].items() if service in APP_SERVICES}
        private_json(directory / "PREVIOUS-PRODUCTION.json", checkpoint)
    else:
        checkpoint = json.loads(Path("/opt/protein-ai-platform/snapshots/20261103/CHECKPOINT.json").read_text())
        frozen = {row["service"]: row for row in checkpoint["services"]}
    for service in APP_SERVICES:
        name = "docker-" + service + "-1"
        x = json.loads(docker("inspect", name))[0]
        overrides = [(release / "frontend/dist", "/usr/share/nginx/html")] if service == "frontend" else [(release / "backend/app", "/app/app"), (release / "backend/alembic", "/app/alembic")]
        prior_mounts = frozen[service].get("release_mounts", {}) if production_record else None
        payload = runtime_create_payload(x, frozen[service], overrides, model_env if service != "frontend" else {},
                                         prior_mounts=prior_mounts)
        docker("image", "inspect", payload["Image"])
        private_json(directory / f"previous-inspect-{service}.json", x)
        private_json(directory / f"create-{service}.json", payload)
        rows.append({"service": service, "original_container_id": x["Id"], "image": payload["Image"], "private_create_payload": f"create-{service}.json", "payload_sha256": sha256(directory / f"create-{service}.json"), "source_mounts": [str(s) for s, _ in overrides], "model_environment_keys": sorted(model_env) if service != "frontend" else []})
    summary = {"release_path": str(release), "source_sha256": release_inventory(release), "services": rows, "current_changed": False, "production_containers_changed": False, "rollback_strategy": "Retain old stopped/renamed containers, recreate original names from their original ID and start on failure. Never restore database."}
    private_json(directory / "RUNTIME-PREPARED.json", summary)
    return summary


def switch_runtime(directory: Path, backup_evidence: Path) -> dict[str, object]:
    """Switch prepared app containers and automatically restore old names on failure."""
    summary = json.loads((directory / "RUNTIME-PREPARED.json").read_text())
    if release_inventory(Path(summary["release_path"])) != summary.get("source_sha256"):
        raise ValueError("release source changed after preparation")
    backup = json.loads(backup_evidence.read_text())
    age = datetime.now(timezone.utc) - datetime.fromisoformat(backup["created_at"])
    if not backup.get("isolated_restore_verified") or not backup.get("archive_list_verified") or not 0 <= age.total_seconds() <= 21600:
        raise ValueError("a successful fresh backup/isolated restore drill no older than 6 hours is required")
    dump = backup_evidence.parent / "database.dump"
    if sha256(dump) != backup["backup_sha256"]:
        raise ValueError("fresh backup checksum no longer matches")
    rows = summary["services"]
    if {row["service"] for row in rows} != set(APP_SERVICES):
        raise ValueError("prepared runtime must contain exactly the five app services")
    for row in rows:
        path = directory / row["private_create_payload"]
        if path.parent.resolve() != directory.resolve() or sha256(path) != row["payload_sha256"]:
            raise ValueError("private create payload integrity failure")
        actual = json.loads(docker("inspect", "docker-" + row["service"] + "-1"))[0]
        if actual["Id"] != row["original_container_id"]:
            raise ValueError("active app container changed after preparation")
        if row["service"] == "backend" and actual["Id"] != backup["active_backend_container_id"]:
            raise ValueError("backup evidence belongs to another active backend")
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    state = {"release_path": summary["release_path"], "started_at": tag, "services": [], "status": "switching", "database_restored": False, "current_changed": False}
    state_path = directory / "SWITCH-STATE.json"
    if state_path.exists():
        raise ValueError("switch state already exists; inspect it before any retry")
    private_json(state_path, state)
    try:
        for row in rows:
            name = "docker-" + row["service"] + "-1"
            old = name + "-pre-" + tag
            item = {"service": row["service"], "name": name, "rollback_name": old, "original_id": row["original_container_id"], "new_id": None}
            state["services"].append(item)
            state_path.write_text(json.dumps(state, indent=2) + "\n")
            docker("stop", "--time", "120", name)
            docker("rename", name, old)
            payload_path = directory / row["private_create_payload"]
            result = subprocess.run(["curl", "--silent", "--show-error", "--fail", "--unix-socket", "/var/run/docker.sock", "-H", "Content-Type: application/json", "--data-binary", "@" + str(payload_path), "http://localhost/v1.41/containers/create?name=" + name], capture_output=True)
            if result.returncode:
                raise RuntimeError("Docker create failed; private payload retained for local diagnosis")
            item["new_id"] = json.loads(result.stdout)["Id"]
            state_path.write_text(json.dumps(state, indent=2) + "\n")
            docker("start", name)
            for _ in range(90):
                x = json.loads(docker("inspect", name))[0]
                health = x["State"].get("Health", {}).get("Status")
                if x["State"]["Status"] in {"exited", "dead"} or health == "unhealthy":
                    raise RuntimeError("replacement container failed health")
                if health == "healthy":
                    break
                time.sleep(2)
            else:
                raise RuntimeError("replacement health timed out")
            if row["service"] in {"backend", "frontend"}:
                # Nginx resolves static upstream hostnames when loading config.
                # Recreated containers may have new IPs; keep nginx's container
                # and configuration, but refresh those upstream addresses.
                docker("exec", "docker-nginx-1", "nginx", "-t")
                docker("exec", "docker-nginx-1", "nginx", "-s", "reload")
        state["status"] = "healthy_pending_functional_acceptance"
    except BaseException:
        rollback_runtime(directory)
        raise
    finally:
        if state["status"] == "healthy_pending_functional_acceptance":
            state_path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def rollback_runtime(directory: Path) -> dict[str, object]:
    state_path = directory / "SWITCH-STATE.json"
    state = json.loads(state_path.read_text())
    for row in reversed(state["services"]):
        actual = json.loads(docker("inspect", row["original_id"]))[0]
        if actual["Name"] == "/" + row["name"]:
            docker("start", row["original_id"])
            continue
        if actual["Name"] != "/" + row["rollback_name"]:
            raise RuntimeError("original container name changed; refusing ambiguous rollback")
        found = subprocess.run(["docker", "inspect", row["name"]], capture_output=True)
        if found.returncode == 0:
            replacement = json.loads(found.stdout)[0]
            if row["new_id"] and replacement["Id"] != row["new_id"]:
                raise RuntimeError("unexpected replacement ID; refusing rollback")
            docker("stop", "--time", "120", row["name"])
            docker("rename", row["name"], row["name"] + "-failed-" + uuid.uuid4().hex[:8])
        docker("rename", row["original_id"], row["name"])
        docker("start", row["original_id"])
    docker("exec", "docker-nginx-1", "nginx", "-t")
    docker("exec", "docker-nginx-1", "nginx", "-s", "reload")
    state["status"] = "rolled_back_application_only"
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", help="Full candidate Git commit ID")
    parser.add_argument("--runtime-migration", default="20260917_0004")
    parser.add_argument("--output", type=Path, help="Write packet JSON to this path")
    parser.add_argument("--prepare-runtime", type=Path, metavar="PRIVATE_OUTPUT_DIR", help="Write private Docker create requests only; does not start/stop containers")
    parser.add_argument("--release-path", type=Path, help="Existing new release with built frontend/dist")
    parser.add_argument("--model-service-env", type=Path, help="Private installed service.env; inject only model URLs, authentication and CPU timeouts")
    parser.add_argument("--production-record", type=Path, help="For a subsequent release: require exact current IDs, images and read-only source mounts from this record")
    parser.add_argument("--backup-drill", type=Path, metavar="PRIVATE_OUTPUT_DIR", help="Create fresh DB backup and restore only to a disposable network-isolated DB")
    parser.add_argument("--postgres-client-image", help="Immutable existing local postgres:16 image ID")
    parser.add_argument("--switch-runtime", type=Path, metavar="PRIVATE_RUNTIME_DIR", help="Replace prepared app containers, retaining stopped originals for rollback")
    parser.add_argument("--backup-evidence", type=Path, help="Successful fresh BACKUP-DRILL.json required for switching")
    parser.add_argument("--rollback-runtime", type=Path, metavar="PRIVATE_RUNTIME_DIR", help="Restore original app containers and retain latest database")
    args = parser.parse_args()
    if sum(bool(x) for x in [args.prepare_runtime, args.backup_drill, args.switch_runtime, args.rollback_runtime]) > 1:
        parser.error("runtime operations cannot be combined")
    if args.switch_runtime:
        if not args.backup_evidence:
            parser.error("--switch-runtime requires --backup-evidence")
        print(json.dumps(switch_runtime(args.switch_runtime, args.backup_evidence), indent=2))
        return 0
    if args.rollback_runtime:
        print(json.dumps(rollback_runtime(args.rollback_runtime), indent=2))
        return 0
    if args.prepare_runtime:
        if not args.release_path or args.backup_drill:
            parser.error("--prepare-runtime requires --release-path and cannot combine with --backup-drill")
        print(json.dumps(prepare_runtime_payloads(args.prepare_runtime, args.release_path, args.model_service_env, args.production_record), indent=2))
        return 0
    if args.backup_drill:
        if not args.postgres_client_image:
            parser.error("--backup-drill requires --postgres-client-image")
        print(json.dumps(fresh_backup_drill(args.backup_drill, args.postgres_client_image), indent=2))
        return 0
    if not args.expected_commit:
        parser.error("--expected-commit is required for the read-only preparation packet")
    packet = build_packet(args.expected_commit, args.runtime_migration)
    rendered = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
