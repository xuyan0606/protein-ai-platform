#!/usr/bin/env python3
"""Live smoke for admin APIs, logged-in tool metadata, and OIDC provider flow.

This script intentionally never prints passwords, access tokens, refresh tokens,
OIDC codes, id_tokens, or bearer tokens.
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_ADMIN_CREDENTIAL_FILE = "/opt/protein-ai-platform/shared/secrets/admin-initial-credentials.txt"
DEFAULT_CLIENT_ID = "protein-ai"
DEFAULT_CLIENT_SECRET = "oidc-secret-change-me-in-production"


class SmokeFailure(AssertionError):
    pass


def _read_env_file_value(paths: List[str], name: str, default: str = "") -> str:
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == name:
                return value.strip().strip("'\"")
    return default


def _read_admin_credentials(path: str) -> Tuple[str, str]:
    env_email = os.getenv("ADMIN_LIVE_EMAIL")
    env_password = os.getenv("ADMIN_LIVE_PASSWORD")
    if env_email and env_password:
        return env_email, env_password

    text = Path(path).read_text(encoding="utf-8", errors="replace")
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", text)
    password = None
    for line in text.splitlines():
        lower = line.lower()
        if "password" in lower or "密码" in line:
            if ":" in line:
                password = line.split(":", 1)[1].strip()
            elif "=" in line:
                password = line.split("=", 1)[1].strip()
            else:
                parts = line.split()
                password = parts[-1] if parts else None
            break
    if not email_match or not password:
        raise SmokeFailure("Unable to parse admin credentials")
    return email_match.group(0), password


def _request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    token: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    expected: Optional[int] = None,
) -> Tuple[int, Dict[str, Any]]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
            status = response.status
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type and payload:
                parsed = json.loads(payload.decode("utf-8"))
            else:
                parsed = {"bytes": len(payload), "content_type": content_type}
    except urllib.error.HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError:
            parsed = {"body": text[:200]}
    if expected is not None and status != expected:
        raise SmokeFailure(f"{path} returned HTTP {status}, expected {expected}: {parsed}")
    return status, parsed


def _request_form(
    base_url: str,
    path: str,
    *,
    form: Dict[str, str],
    expected: Optional[int] = None,
) -> Tuple[int, Dict[str, Any]]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urllib.parse.urlencode(form).encode("utf-8")
    request = urllib.request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        status = exc.code
        parsed = json.loads(exc.read().decode("utf-8", errors="replace") or "{}")
    if expected is not None and status != expected:
        raise SmokeFailure(f"{path} returned HTTP {status}, expected {expected}: {parsed}")
    return status, parsed


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401, ANN001
        return None


def _oidc_authorize_no_redirect(base_url: str, token: str, params: Dict[str, str]) -> str:
    opener = urllib.request.build_opener(_NoRedirect)
    url = base_url.rstrip() + "/api/oidc/authorize?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Cookie": "pa_token=" + token}, method="GET")
    try:
        opener.open(request, timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code not in {302, 303, 307, 308}:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SmokeFailure(f"/api/oidc/authorize returned HTTP {exc.code}: {detail[:300]}")
        location = exc.headers.get("Location", "")
        if not location:
            raise SmokeFailure(f"/api/oidc/authorize returned HTTP {exc.code} without Location")
        return location
    raise SmokeFailure("/api/oidc/authorize did not redirect")


def run(args: argparse.Namespace) -> Dict[str, Any]:
    base_url = args.base_url.rstrip("/")
    admin_email, admin_password = _read_admin_credentials(args.admin_credentials_file)
    oidc_secret = (
        args.oidc_client_secret
        or os.getenv("OIDC_CLIENT_SECRET")
        or _read_env_file_value(args.env_file, "OIDC_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
    )

    checks: Dict[str, Any] = {}
    _, admin_login = _request_json(
        base_url,
        "/api/auth/login",
        method="POST",
        body={"email": admin_email, "password": admin_password},
        expected=200,
    )
    admin_token = admin_login["access_token"]
    if admin_login["user"]["role"] != "admin":
        raise SmokeFailure("Admin login did not return admin role")
    checks["admin_login"] = 200

    temp_email = f"admin_live_gate_{int(time.time())}@example.com"
    temp_password = "AdminLiveGate123!"
    _, temp_login = _request_json(
        base_url,
        "/api/auth/register",
        method="POST",
        body={"email": temp_email, "password": temp_password, "name": "Admin Live Gate"},
        expected=201,
    )
    temp_token = temp_login["access_token"]
    temp_id = int(temp_login["user"]["id"])
    checks["temp_user_registered"] = 201

    checks["researcher_admin_users_forbidden"] = _request_json(
        base_url, "/api/auth/admin/users", token=temp_token, expected=403
    )[0]
    checks["admin_ping"] = _request_json(base_url, "/api/auth/admin/ping", token=admin_token, expected=200)[0]

    _, users = _request_json(base_url, "/api/auth/admin/users?limit=50", token=admin_token, expected=200)
    checks["admin_users_count"] = users.get("count", 0)
    if not any(user.get("email") == temp_email for user in users.get("users", [])):
        raise SmokeFailure("Temporary user missing from admin user list")

    _, promoted = _request_json(
        base_url,
        f"/api/auth/admin/users/{temp_id}/role",
        method="PATCH",
        token=admin_token,
        body={"role": "admin"},
        expected=200,
    )
    if promoted.get("role") != "admin":
        raise SmokeFailure("Temporary user promotion failed")
    _, demoted = _request_json(
        base_url,
        f"/api/auth/admin/users/{temp_id}/role",
        method="PATCH",
        token=admin_token,
        body={"role": "researcher"},
        expected=200,
    )
    if demoted.get("role") != "researcher":
        raise SmokeFailure("Temporary user demotion failed")
    checks["admin_role_update"] = "passed"

    _, locked = _request_json(
        base_url,
        f"/api/auth/admin/users/{temp_id}/status",
        method="PATCH",
        token=admin_token,
        body={"locked": True},
        expected=200,
    )
    if not locked.get("locked_at"):
        raise SmokeFailure("Temporary user lock failed")
    checks["locked_login_forbidden"] = _request_json(
        base_url,
        "/api/auth/login",
        method="POST",
        body={"email": temp_email, "password": temp_password},
        expected=403,
    )[0]
    _, unlocked = _request_json(
        base_url,
        f"/api/auth/admin/users/{temp_id}/status",
        method="PATCH",
        token=admin_token,
        body={"locked": False},
        expected=200,
    )
    if unlocked.get("locked_at") is not None:
        raise SmokeFailure("Temporary user unlock failed")

    _, disabled = _request_json(
        base_url,
        f"/api/auth/admin/users/{temp_id}/status",
        method="PATCH",
        token=admin_token,
        body={"is_active": False, "disabled_reason": "live gate"},
        expected=200,
    )
    if disabled.get("is_active") is not False:
        raise SmokeFailure("Temporary user disable failed")
    checks["disabled_login_forbidden"] = _request_json(
        base_url,
        "/api/auth/login",
        method="POST",
        body={"email": temp_email, "password": temp_password},
        expected=403,
    )[0]
    _, enabled = _request_json(
        base_url,
        f"/api/auth/admin/users/{temp_id}/status",
        method="PATCH",
        token=admin_token,
        body={"is_active": True},
        expected=200,
    )
    if enabled.get("is_active") is not True:
        raise SmokeFailure("Temporary user enable failed")
    checks["admin_status_update"] = "passed"

    for path in [
        "/api/tools",
        "/api/tools/gromacs_md",
        "/api/tools/diagnostics",
        "/api/tools/md/protocols",
        "/api/chat/models",
    ]:
        _, payload = _request_json(base_url, path, token=temp_token, expected=200)
        checks[path] = 200
        if path == "/api/tools" and not payload.get("tools"):
            raise SmokeFailure("Tool list is empty")
        if path == "/api/tools/gromacs_md" and payload.get("name") != "gromacs_md":
            raise SmokeFailure("gromacs_md metadata response is incorrect")

    checks["admin_task_audits"] = _request_json(
        base_url, "/api/tools/admin/tasks/audits?limit=5", token=admin_token, expected=200
    )[0]
    checks["admin_task_summary"] = _request_json(
        base_url, "/api/tools/admin/tasks/audits/summary?limit=50", token=admin_token, expected=200
    )[0]
    _, export_payload = _request_json(
        base_url, "/api/tools/admin/tasks/audits/export?limit=20", token=admin_token, expected=200
    )
    checks["admin_audit_csv_bytes"] = export_payload.get("bytes", 0)
    checks["data_readiness"] = _request_json(
        base_url, "/api/data/admin/readiness", token=admin_token, expected=200
    )[0]
    checks["data_updates"] = _request_json(
        base_url, "/api/data/admin/updates?limit=10", token=admin_token, expected=200
    )[0]
    checks["data_import_dry_run"] = _request_json(
        base_url,
        "/api/data/admin/import",
        method="POST",
        token=admin_token,
        body={"dry_run": True, "symlink": True},
        expected=200,
    )[0]

    redirect_uri = f"{base_url}/wiki/auth/oidc.callback"
    location = _oidc_authorize_no_redirect(
        base_url,
        admin_token,
        {
            "client_id": args.oidc_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
            "state": "live-gate-state",
            "nonce": "live-gate-nonce",
        },
    )
    parsed = urllib.parse.urlparse(location)
    query = urllib.parse.parse_qs(parsed.query)
    if query.get("state", [""])[0] != "live-gate-state" or not query.get("code"):
        raise SmokeFailure("OIDC authorize redirect missing code/state")
    checks["oidc_authorize_redirect"] = 302

    _, token_payload = _request_form(
        base_url,
        "/api/oidc/token",
        form={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "client_id": args.oidc_client_id,
            "client_secret": oidc_secret,
            "redirect_uri": redirect_uri,
        },
        expected=200,
    )
    if not token_payload.get("access_token") or not token_payload.get("id_token"):
        raise SmokeFailure("OIDC token response missing access_token/id_token")
    _, userinfo = _request_json(
        base_url,
        "/api/oidc/userinfo",
        token=token_payload["access_token"],
        expected=200,
    )
    if userinfo.get("email") != admin_email:
        raise SmokeFailure("OIDC userinfo did not return admin user")
    checks["oidc_token"] = 200
    checks["oidc_userinfo"] = 200
    checks["oidc_jwks"] = _request_json(base_url, "/api/oidc/jwks", expected=200)[0]

    # Leave the temporary user disabled after the gate.
    _request_json(
        base_url,
        f"/api/auth/admin/users/{temp_id}/status",
        method="PATCH",
        token=admin_token,
        body={"is_active": False, "disabled_reason": "live gate completed"},
        expected=200,
    )

    return {
        "status": "passed",
        "admin_api": "passed",
        "tools_logged_in_metadata": "passed",
        "oidc_provider_round_trip": "passed",
        "temp_user_id": temp_id,
        "temp_user_final_state": "disabled",
        "checks": checks,
        "tokens_printed": False,
        "passwords_printed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1"))
    parser.add_argument("--admin-credentials-file", default=os.getenv("ADMIN_CREDENTIALS_FILE", DEFAULT_ADMIN_CREDENTIAL_FILE))
    parser.add_argument("--oidc-client-id", default=os.getenv("OIDC_CLIENT_ID", DEFAULT_CLIENT_ID))
    parser.add_argument("--oidc-client-secret", default=None)
    parser.add_argument(
        "--env-file",
        action="append",
        default=[
            "/opt/protein-ai-platform/current/docker/.env.aliyun.app",
            "/opt/protein-ai-platform/current/docker/.env",
        ],
    )
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
