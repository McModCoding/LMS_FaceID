"""Read-only import/hash smoke test; run inside the Docker backend image."""
from __future__ import annotations

import importlib.metadata

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.face.factory import get_engine
from app.main import app


def main() -> int:
    # Pydantic's EmailStr is exercised by importing app.main, not only pydantic.
    import email_validator  # noqa: F401

    sample = "LocalDemo!2026"
    digest = get_password_hash(sample)
    assert digest.startswith("$2")
    assert verify_password(sample, digest) and not verify_password("wrong", digest)

    engine = get_engine()
    if settings.FACE_ENGINE == "opencv" and not settings.FACE_EMBEDDING_KEY.strip():
        raise RuntimeError("FACE_ENGINE=opencv requires FACE_EMBEDDING_KEY to protect biometric data")
    print(f"Face engine configured: {engine.name} (real models checked later)")

    paths = app.openapi()["paths"]
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/register" not in paths
    print("PASS: FastAPI import, email validation, password hash/verify, login route, no public signup")
    print("bcrypt:", importlib.metadata.version("bcrypt"))
    print("email-validator:", importlib.metadata.version("email-validator"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
