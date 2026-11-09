#!/usr/bin/env python3
"""Black-box smoke for per-user content isolation.

Reads user credentials from stdin JSON. Passwords are never printed.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar


class ApiClient:
    def __init__(self, base_url, email, password):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.cookies = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(self, method, path, data=None, ok=(200,)):
        body = None
        headers = {}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as resp:
                raw = resp.read()
                payload = json.loads(raw.decode("utf-8")) if raw else None
                if resp.status not in ok:
                    raise AssertionError(f"{method} {path} expected {ok}, got {resp.status}: {payload}")
                return resp.status, payload
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                payload = json.loads(raw.decode("utf-8")) if raw else None
            except Exception:
                payload = raw.decode("utf-8", errors="ignore")
            if exc.code not in ok:
                raise AssertionError(f"{method} {path} expected {ok}, got {exc.code}: {payload}")
            return exc.code, payload

    def login(self):
        _, payload = self.request(
            "POST",
            "/api/auth/login",
            {"email": self.email, "password": self.password},
            ok=(200,),
        )
        user = payload["user"]
        return {"id": int(user["id"]), "email": user["email"], "role": user.get("role")}


def _load_users():
    data = json.loads(sys.stdin.read())
    if not isinstance(data, list) or len(data) < 2:
        raise SystemExit("stdin JSON must contain at least two users")
    for user in data:
        if not user.get("email") or not user.get("password"):
            raise SystemExit("each user needs email and password")
    return data


def _ids(items):
    return {item["id"] for item in items}


def run(base_url, users):
    clients = [ApiClient(base_url, user["email"], user["password"]) for user in users]
    login_rows = [client.login() for client in clients]
    steps = []

    for row in login_rows:
        if row["role"] != "researcher":
            raise AssertionError(f"{row['email']} role must be researcher, got {row['role']}")
    steps.append({"name": "login_roles", "status": "passed", "count": len(login_rows)})

    for client in clients:
        client.request("GET", "/api/auth/admin/users", ok=(403,))
    steps.append({"name": "admin_api_forbidden_for_researchers", "status": "passed"})

    stamp = int(time.time())
    conv_ids = []
    project_ids = []
    try:
        for idx, client in enumerate(clients[:2], start=1):
            _, conv = client.request(
                "POST",
                "/api/conversations",
                {"title": f"isolation-smoke-{stamp}-user-{idx}"},
                ok=(201,),
            )
            conv_ids.append(conv["id"])
            _, project = client.request(
                "POST",
                "/api/projects",
                {
                    "name": f"isolation-smoke-{stamp}-user-{idx}",
                    "description": "temporary isolation smoke project",
                    "wiki_auto_publish": False,
                },
                ok=(201,),
            )
            project_ids.append(project["id"])

        _, convs_1 = clients[0].request("GET", "/api/conversations")
        _, convs_2 = clients[1].request("GET", "/api/conversations")
        if conv_ids[0] not in _ids(convs_1) or conv_ids[1] in _ids(convs_1):
            raise AssertionError("conversation list isolation failed for first user")
        if conv_ids[1] not in _ids(convs_2) or conv_ids[0] in _ids(convs_2):
            raise AssertionError("conversation list isolation failed for second user")
        clients[1].request("GET", f"/api/conversations/{conv_ids[0]}", ok=(404,))
        clients[0].request("GET", f"/api/conversations/{conv_ids[1]}", ok=(404,))
        steps.append({"name": "conversation_isolation", "status": "passed"})

        _, projects_1 = clients[0].request("GET", "/api/projects")
        _, projects_2 = clients[1].request("GET", "/api/projects")
        if project_ids[0] not in _ids(projects_1) or project_ids[1] in _ids(projects_1):
            raise AssertionError("project list isolation failed for first user")
        if project_ids[1] not in _ids(projects_2) or project_ids[0] in _ids(projects_2):
            raise AssertionError("project list isolation failed for second user")
        clients[1].request("GET", f"/api/projects/{project_ids[0]}", ok=(404,))
        clients[0].request("GET", f"/api/projects/{project_ids[1]}", ok=(404,))
        steps.append({"name": "project_isolation", "status": "passed"})
    finally:
        for client, conv_id in zip(clients[:2], conv_ids):
            try:
                client.request("DELETE", f"/api/conversations/{conv_id}", ok=(204, 404))
            except Exception:
                pass
        for client, project_id in zip(clients[:2], project_ids):
            try:
                client.request("DELETE", f"/api/projects/{project_id}", ok=(204, 404))
            except Exception:
                pass

    return {
        "status": "passed",
        "base_url": base_url,
        "users_checked": [{"email": row["email"], "id": row["id"], "role": row["role"]} for row in login_rows],
        "steps": steps,
        "passwords_printed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://120.27.108.138")
    args = parser.parse_args()
    users = _load_users()
    payload = run(args.base_url, users)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
