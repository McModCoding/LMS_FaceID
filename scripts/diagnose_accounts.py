"""Read-only assessment of demo accounts. Never prints stored hashes or secrets."""
from __future__ import annotations

from app.core.security import verify_password
from app.db.session import SessionLocal
from app.models.user import User


def main() -> int:
    db = SessionLocal()
    try:
        print(f"total_users={db.query(User).count()}")
        cases = (("admin", "Demo@123"), ("gv001", "Demo@123"),
                 ("gv002", "DevPass@123"), ("sv001", "Demo@123"),
                 ("sv002", "DevPass@123"))
        for username, password in cases:
            user = db.query(User).filter(User.username == username).first()
            if user is None:
                print(f"{username}: NOT_FOUND")
                continue
            try:
                matches = verify_password(password, user.password_hash)
                match_text = "MATCH" if matches else "DIFFERENT_PASSWORD"
            except Exception as exc:
                match_text = f"VERIFY_ERROR({type(exc).__name__})"
            print(f"{username}: role={user.role.value} active={user.is_active} "
                  f"deleted={user.is_deleted} demo_password={match_text}")
    finally:
        db.close()
    print("READ_ONLY: no accounts or passwords changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
