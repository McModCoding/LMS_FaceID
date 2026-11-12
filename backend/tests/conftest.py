import contextlib
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.main import app
from app.models.user import User, UserRole

# --- Safety Guard ---
TEST_DB_NAME = os.environ.get("TEST_DB_NAME", "lms_test")
assert "test" in TEST_DB_NAME.lower(), (
    f"CẢNH BÁO NGUY HIỂM: Tên database test '{TEST_DB_NAME}' phải chứa từ 'test'!"
)
TEST_DB_ADMIN_USER = os.environ.get("TEST_DB_ADMIN_USER")
TEST_DB_ADMIN_PASSWORD = os.environ.get("TEST_DB_ADMIN_PASSWORD")
TEST_KEEP_DB = os.environ.get("TEST_KEEP_DB") == "1"

TEST_DB_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{TEST_DB_NAME}?charset=utf8mb4"
)

ADMIN_DB_URL = (
    f"mysql+pymysql://{TEST_DB_ADMIN_USER}:{TEST_DB_ADMIN_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}?charset=utf8mb4"
    if TEST_DB_ADMIN_USER and TEST_DB_ADMIN_PASSWORD
    else None
)


def _is_mysql_available() -> bool:
    if not ADMIN_DB_URL:
        return False

    try:
        engine = create_engine(ADMIN_DB_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


_USE_MYSQL = _is_mysql_available() and not os.environ.get("USE_SQLITE")
if os.environ.get("REQUIRE_MYSQL_TESTS") == "1" and not _USE_MYSQL:
    raise RuntimeError("MySQL test không khả dụng; dừng để tránh chuyển sang SQLite.")


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Tạo database test, chạy migration / create_all và dọn dẹp sau khi xong."""
    if _USE_MYSQL:
        # 1. Tạo database MySQL nếu chưa có
        root_engine = create_engine(ADMIN_DB_URL)
        with root_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{TEST_DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        root_engine.dispose()

        # 2. Chạy alembic upgrade head trên database test
        test_env = os.environ.copy()
        test_env["DB_NAME"] = TEST_DB_NAME
        backend_dir = str(Path(__file__).resolve().parent.parent)
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=test_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Chạy Alembic migration cho test DB thất bại:\n{result.stderr}\n{result.stdout}")

        yield

        # 3. CI dọn database test; khi debug có thể giữ lại bằng TEST_KEEP_DB=1.
        if not TEST_KEEP_DB:
            cleanup_engine = create_engine(ADMIN_DB_URL)
            with cleanup_engine.connect() as conn:
                conn.execute(text(f"DROP DATABASE IF EXISTS `{TEST_DB_NAME}`"))
            cleanup_engine.dispose()
    else:
        # Dùng SQLite file cho test
        sqlite_file = Path(__file__).resolve().parent.parent / "test_local.db"
        if sqlite_file.exists():
            sqlite_file.unlink()
        engine = create_engine(f"sqlite:///{sqlite_file}")
        Base.metadata.create_all(engine)
        engine.dispose()

        yield

        if sqlite_file.exists():
            with contextlib.suppress(Exception):
                sqlite_file.unlink()


@pytest.fixture(scope="session")
def test_engine(setup_test_database):
    if _USE_MYSQL:
        engine = create_engine(TEST_DB_URL, pool_pre_ping=True, isolation_level="READ COMMITTED")
    else:
        sqlite_file = Path(__file__).resolve().parent.parent / "test_local.db"
        engine = create_engine(f"sqlite:///{sqlite_file}")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def TestingSessionLocal(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session(TestingSessionLocal):
    """Mỗi test function có 1 session riêng biệt, rollback sau khi hoàn thành."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def test_client(test_engine, setup_test_database, TestingSessionLocal):
    """FastAPI TestClient kết nối thẳng vào database test qua dependency override."""
    from app.core.deps import get_db

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # The production scheduler uses SessionLocal, not the get_db override.
    # Do not let tests start jobs against the configured application database.
    with patch("app.main.start_scheduler"), patch("app.main.stop_scheduler"), TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_token(db_session):
    """Đảm bảo tài khoản admin tồn tại trong test DB và trả về JWT Bearer token."""
    admin = db_session.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@lmstest.local",
            password_hash=get_password_hash("Demo@123"),
            role=UserRole.admin,
            is_active=True,
            must_change_password=False,
            is_deleted=False,
            token_version=1,
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
    return create_access_token({"sub": str(admin.id), "role": admin.role.value, "token_version": admin.token_version})


@pytest.fixture(scope="function")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
