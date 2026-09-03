#!/usr/bin/env python3
"""Create or update local platform users from stdin JSON without printing passwords."""

import argparse
import asyncio
import json
import os
import sys


def _backend_path() -> str:
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "backend"),
        "/app",
    ]
    for candidate in candidates:
        if os.path.isdir(os.path.join(candidate, "app")):
            return candidate
    return candidates[0]


sys.path.insert(0, _backend_path())


async def ensure_users(users, role):
    from sqlalchemy import select

    from app.core.database import _async_session_factory, init_db
    from app.models.user import User

    await init_db()
    result_rows = []
    async with _async_session_factory() as db:
        for item in users:
            email = str(item["email"]).strip().lower()
            password = str(item["password"])
            name = str(item.get("name") or email.split("@")[0]).strip()
            if not email or not password:
                raise ValueError("email and password are required")

            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(
                    email=email,
                    name=name,
                    hashed_password=User.hash_password(password),
                    role=role,
                    is_active=True,
                    locked_at=None,
                    disabled_reason=None,
                )
                db.add(user)
                action = "created"
            else:
                user.name = name
                user.hashed_password = User.hash_password(password)
                user.role = role
                user.is_active = True
                user.locked_at = None
                user.disabled_reason = None
                action = "updated"
            await db.flush()
            result_rows.append({"email": email, "id": int(user.id), "role": user.role, "action": action})
        await db.commit()
    return result_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", default="researcher", choices=["researcher", "admin"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    users = json.loads(sys.stdin.read())
    if not isinstance(users, list):
        raise SystemExit("stdin JSON must be a list")
    result = asyncio.run(ensure_users(users, args.role))
    payload = {"status": "ok", "count": len(result), "users": result, "passwords_printed": False}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("status\tok")
        for row in result:
            print("{email}\t{id}\t{role}\t{action}".format(**row))
        print("passwords_printed\tfalse")


if __name__ == "__main__":
    main()
