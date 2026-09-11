"""Command-line utilities for project setup and administrative bootstrap."""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal, init_db
from app.models.user import Role, User
from app.core.security import hash_password


def _validate_password(password: str) -> str:
    """Validate a candidate password for admin bootstrap."""
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters long.")
    if password.strip() != password:
        raise ValueError("Password cannot start or end with whitespace.")
    if not any(ch.isupper() for ch in password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not any(ch.islower() for ch in password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("Password must contain at least one number.")
    if not any(not ch.isalnum() for ch in password):
        raise ValueError("Password must contain at least one special character.")
    return password


def create_admin_account(db: Session, username: str, email: str, password: str) -> User:
    """Create a secure admin user if one does not already exist."""
    normalized_username = username.strip()
    normalized_email = email.strip().lower()
    if not normalized_username or not normalized_email:
        raise ValueError("Username and email are required.")

    existing = db.query(User).filter((User.username == normalized_username) | (User.email == normalized_email)).first()
    if existing:
        raise ValueError("A user with that username or email already exists.")

    _validate_password(password)

    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if admin_role is None:
        user_role = db.query(Role).filter(Role.name == "user").first()
        if user_role is None:
            user_role = Role(name="user", description="Regular user")
            db.add(user_role)
            db.flush()
        admin_role = Role(name="admin", description="Administrator with full access")
        db.add(admin_role)
        db.flush()

    user = User(
        username=normalized_username,
        email=normalized_email,
        hashed_password=hash_password(password),
        first_name="System",
        last_name="Admin",
        is_active=True,
    )
    user.roles.append(admin_role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _prompt_admin_details() -> tuple[str, str, str]:
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip()
    while True:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match. Please try again.")
            continue
        try:
            _validate_password(password)
            return username, email, password
        except ValueError as exc:
            print(f"Password validation failed: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the initial platform administrator.")
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--email", help="Admin email")
    parser.add_argument("--password", help="Admin password")
    args = parser.parse_args()

    try:
        db = SessionLocal()
        try:
            init_db()
            if args.username and args.email and args.password:
                user = create_admin_account(db, args.username, args.email, args.password)
                print(f"Created administrator: {user.username} ({user.email})")
                return 0

            username, email, password = _prompt_admin_details()
            user = create_admin_account(db, username, email, password)
            print(f"Created administrator: {user.username} ({user.email})")
            return 0
        finally:
            db.close()
    except ValueError as exc:
        print(f"Admin setup failed: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
