from app.core.security import get_password_hash
from app.models.audit import AuditLog
from app.models.user import User, UserRole


def test_audit_logs_content_and_single_record(test_client, admin_headers, db_session):
    # 1. Tạo user sv_audit_test
    test_user = User(
        username="sv_audit_test",
        email="sv_audit_test@lmstest.local",
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

    count_before = db_session.query(AuditLog).filter(
        AuditLog.action == "TOGGLE_USER_STATUS",
        AuditLog.entity_id == str(user_id),
    ).count()

    # 2. Khóa tài khoản với X-Forwarded-For IP
    headers = {**admin_headers, "X-Forwarded-For": "203.0.113.195, 10.0.0.1"}
    resp = test_client.patch(
        f"/api/v1/users/{user_id}/status",
        json={"is_active": False},
        headers=headers,
    )
    assert resp.status_code == 200

    # 3. Kiểm tra chỉ tạo ĐÚNG 1 bản ghi nhật ký
    db_session.rollback()
    logs = db_session.query(AuditLog).filter(
        AuditLog.action == "TOGGLE_USER_STATUS",
        AuditLog.entity_id == str(user_id),
    ).all()
    assert len(logs) == count_before + 1

    latest_log = logs[-1]
    assert latest_log.ip == "203.0.113.195"
    assert latest_log.detail is not None
    assert latest_log.detail["target_username"] == "sv_audit_test"
    assert latest_log.detail["old_is_active"] is True
    assert latest_log.detail["new_is_active"] is False
    assert "summary" in latest_log.detail

    # 4. Test Reset Password: Tuyệt đối KHÔNG chứa mật khẩu/hash trong detail
    reset_resp = test_client.post(
        f"/api/v1/users/{user_id}/reset-password",
        headers=headers,
    )
    assert reset_resp.status_code == 200
    temp_pwd = reset_resp.json()["temp_password"]

    db_session.rollback()
    reset_log = db_session.query(AuditLog).filter(
        AuditLog.action == "RESET_PASSWORD",
        AuditLog.entity_id == str(user_id),
    ).order_by(AuditLog.id.desc()).first()

    assert reset_log is not None
    detail_str = str(reset_log.detail)
    assert temp_pwd not in detail_str
    assert "password" not in reset_log.detail or reset_log.detail["password"] == "[REDACTED]"
