"""Create a StockWise System Admin (platform staff). There is no web signup for this role.

Usage (from backend/, with DATABASE_URL pointing at the database):
    python -m scripts.create_system_admin --email you@example.com --name "Your Name"

The password is asked for twice and never shown. For scripts, it can come from the
SYSTEM_ADMIN_PASSWORD environment variable instead.
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import func, select

import app.config  # noqa: F401  (loads .env)
from app.activity import record
from app.database import SessionLocal
from app.migrate import upgrade_to_head
from app.models import Role, User
from app.security import hash_password


def read_password() -> str:
    pw = os.getenv("SYSTEM_ADMIN_PASSWORD", "")
    if not pw:
        pw = getpass.getpass("Password (at least 8 characters): ")
        if pw != getpass.getpass("Type it again: "):
            sys.exit("The passwords don't match.")
    if len(pw) < 8:
        sys.exit("The password must be at least 8 characters.")
    return pw


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a StockWise System Admin account.")
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", required=True)
    args = ap.parse_args()
    email = args.email.strip().lower()
    if "@" not in email:
        sys.exit("Enter a valid email address.")

    upgrade_to_head()
    with SessionLocal() as db:
        if db.execute(select(User.id).where(func.lower(User.email) == email)).first():
            sys.exit("That email already has an account.")
        user = User(business_id=None, name=args.name.strip(), email=email,
                    password_hash=hash_password(read_password()), role=Role.SYSTEM_ADMIN)
        db.add(user)
        db.flush()
        record(db, user, "system_admin.created", "user", user.id,
               f"System Admin account created for {user.name} from the server")
        db.commit()
    print(f"System Admin {email} created. Log in at the normal login page.")


if __name__ == "__main__":
    main()
