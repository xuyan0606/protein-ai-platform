#!/usr/bin/env python3
"""Reset or create a user account for the Protein AI Platform.

Usage (on ECS server):
  # Reset password for existing user
  python scripts/reset_user.py --email admin@example.com --password newpass123

  # Create new user (or reset if exists)
  python scripts/reset_user.py --email admin@example.com --password newpass123 --name Admin --create

  # List all users
  python scripts/reset_user.py --list

Environment:
  DATABASE_URL must be set, or defaults to local PostgreSQL.
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


async def list_users():
    """List all users in the database."""
    from sqlalchemy import select
    from app.core.database import _async_session_factory, init_db
    from app.models.user import User

    await init_db()

    async with _async_session_factory() as db:
        result = await db.execute(select(User).order_by(User.id))
        users = result.scalars().all()

    if not users:
        print("No users found in database.")
        return

    print(f"{'ID':<5} {'Email':<35} {'Name':<20} {'Created'}")
    print("-" * 80)
    for u in users:
        print(f"{u.id:<5} {u.email:<35} {u.name:<20} {u.created_at}")


async def reset_or_create(email: str, password: str, name: str, create: bool):
    """Reset password or create user."""
    from sqlalchemy import select
    from app.core.database import _async_session_factory, init_db
    from app.models.user import User

    await init_db()

    async with _async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.hashed_password = User.hash_password(password)
            if name:
                user.name = name
            await db.commit()
            print(f"✅ Password reset for: {email} (id={user.id})")
        elif create:
            user = User(
                email=email,
                name=name or email.split("@")[0],
                hashed_password=User.hash_password(password),
            )
            db.add(user)
            await db.commit()
            print(f"✅ User created: {email} (id={user.id}, name={user.name})")
        else:
            print(f"❌ User not found: {email}")
            print(f"   Use --create to create a new account.")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Reset or create user accounts")
    parser.add_argument("--email", help="User email")
    parser.add_argument("--password", help="New password")
    parser.add_argument("--name", default="", help="Display name (for --create)")
    parser.add_argument("--create", action="store_true", help="Create if not exists")
    parser.add_argument("--list", action="store_true", help="List all users")

    args = parser.parse_args()

    if args.list:
        asyncio.run(list_users())
    elif args.email and args.password:
        asyncio.run(reset_or_create(args.email, args.password, args.name, args.create))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
