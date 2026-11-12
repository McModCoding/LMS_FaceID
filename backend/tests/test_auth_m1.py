from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole


def test_lock_and_unlock_user(test_client, admin_headers, db_session):
    # 1. Tạo user sv_lock_test trong test DB
    test_user = db_session.query(User).filter(User.username == "sv_lock_test").first()
    if not test_user:
        test_user = User(
            username="sv_lock_test",
            email="sv_lock_test@lms_test.local",
            password_hash=get_password_hash("Demo@123"),
            role=UserRole.student,
            is_active=True,
            must_change_password=False,
            is_deleted=False,
            token_version=1,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

    user_id = test_user.id

    # 2. Khóa user
    lock_resp = test_client.patch(
        f"/api/v1/users/{user_id}/status",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert lock_resp.status_code == 200
    assert lock_resp.json()["is_active"] is False

    # 3. Đăng nhập thất bại khi tài khoản bị khóa
    login_resp = test_client.post(
        "/api/v1/auth/login",
        json={"username": "sv_lock_test", "password": "Demo@123"},
    )
    assert login_resp.status_code == 401
    assert login_resp.json()["detail"]["code"] == "ACCOUNT_DISABLED"

    # 4. Token cũ bị từ chối
    old_token = create_access_token({"sub": str(user_id), "role": "student", "token_version": 1})
    me_resp = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me_resp.status_code in (401, 403)

    # 5. Mở khóa user
    unlock_resp = test_client.patch(
        f"/api/v1/users/{user_id}/status",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert unlock_resp.status_code == 200
    assert unlock_resp.json()["is_active"] is True

    # 6. Đăng nhập lại thành công sau khi mở khóa
    login_resp2 = test_client.post(
        "/api/v1/auth/login",
        json={"username": "sv_lock_test", "password": "Demo@123"},
    )
    assert login_resp2.status_code == 200
    assert "access_token" in login_resp2.json()


def test_change_password_and_token_revocation(test_client, db_session):
    # Tạo user để test đổi mật khẩu
    user = db_session.query(User).filter(User.username == "sv_pwd_test").first()
    if not user:
        user = User(
            username="sv_pwd_test",
            email="sv_pwd_test@lms_test.local",
            password_hash=get_password_hash("OldPass@123"),
            role=UserRole.student,
            is_active=True,
            must_change_password=True,
            is_deleted=False,
            token_version=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    old_token = create_access_token({"sub": str(user.id), "role": "student", "token_version": user.token_version})

    # Đổi mật khẩu
    change_resp = test_client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "OldPass@123", "new_password": "NewPass@456"},
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert change_resp.status_code == 200
    new_data = change_resp.json()
    assert "access_token" in new_data

    # Token cũ bị từ chối do token_version đã tăng
    me_resp = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me_resp.status_code in (401, 403)

    # Token mới hoạt động bình thường
    new_token = new_data["access_token"]
    me_resp2 = test_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_resp2.status_code == 200
    assert me_resp2.json()["username"] == "sv_pwd_test"
