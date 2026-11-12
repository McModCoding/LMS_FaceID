"""Seed ONLY an empty local teaching database; never reset existing users."""
from __future__ import annotations

import sys

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User


def main() -> int:
    if settings.APP_ENV != "development":
        print("REFUSED: demo seed requires APP_ENV=development (no database changed).")
        return 2
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
    except Exception as exc:
        print(f"ERROR: could not read users table: {type(exc).__name__}")
        return 3
    finally:
        db.close()
    if user_count:
        print(f"REFUSED: database already has {user_count} users. No seed, no password resets.")
        print("Use the Admin UI for additional accounts; see DIAGNOSE_LMS_WINDOWS.bat.")
        return 4
    from app.seed_data import seed_data

    try:
        seed_data()
    except Exception as exc:
        print(f"ERROR: demo seed failed ({type(exc).__name__}); review backend logs.")
        return 5
    print("PASS: demo seed completed on previously empty database.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
