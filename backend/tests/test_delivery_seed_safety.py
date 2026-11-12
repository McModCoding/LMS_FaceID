"""Regression: a repeated seed must never reset an account password/status."""

from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from app.seed_data import get_or_create_user


def test_repeat_seed_preserves_modified_password_and_deactivated_account(db_session):
    user = User(
        username="gv_seed_safety", email="gv_seed_safety@example.test",
        password_hash=get_password_hash("ChangedSafe@2026"),
        role=UserRole.lecturer, is_active=False, must_change_password=True,
        is_deleted=False, token_version=3,
    )
    db_session.add(user)
    db_session.flush()
    old_hash = user.password_hash
    reused = get_or_create_user(db_session, user.username, user.email, user.role, "Demo@123")
    db_session.flush()
    assert reused.id == user.id
    assert reused.password_hash == old_hash
    assert verify_password("ChangedSafe@2026", reused.password_hash)
    assert not verify_password("Demo@123", reused.password_hash)
    assert not reused.is_active
    assert reused.must_change_password
    assert reused.token_version == 3
