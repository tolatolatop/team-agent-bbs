"""
Migration script: hash all existing plaintext passwords and
add expires_at to existing tokens.

Usage:
    python -m team_bbs.migrate_passwords

This script:
  1. Reads all users from the database
  2. Replaces any plaintext password with its bcrypt hash
  3. Adds expires_at (now + DEFAULT_TOKEN_TTL) for any token that has NULL expires_at
"""
import sys
from datetime import UTC, datetime

import bcrypt
from sqlalchemy import select, update

# Need to set up the environment before importing the app
from .db import SessionLocal
from .models import DEFAULT_TOKEN_TTL, Token, User


def migrate_users() -> int:
    """Hash all plaintext passwords that aren't already bcrypt hashes."""
    count = 0
    with SessionLocal.begin() as db:
        users = db.execute(select(User)).scalars().all()
        for user in users:
            pw = user.password
            # Detect if already hashed: bcrypt hashes start with $2b$ or $2a$
            if pw.startswith("$2"):
                continue
            # Hash it
            hashed = bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user.password = hashed
            count += 1
            print(f"  Migrated user #{user.id} ({user.username})")
    return count


def migrate_tokens() -> int:
    """Set expires_at on tokens that have None."""
    count = 0
    with SessionLocal.begin() as db:
        tokens = db.execute(select(Token).where(Token.expires_at.is_(None))).scalars().all()
        now = datetime.now(UTC)
        for token in tokens:
            token.expires_at = now + DEFAULT_TOKEN_TTL
            count += 1
            print(f"  Set expiry on token #{token.id} for user #{token.user_id}")
    return count


def main() -> None:
    print("=== Password Migration ===")
    user_count = migrate_users()
    print(f"Hashed {user_count} user password(s).")

    print("\n=== Token Expiry Migration ===")
    token_count = migrate_tokens()
    print(f"Set expiry on {token_count} token(s).")

    print("\nMigration complete.")


if __name__ == "__main__":
    main()
