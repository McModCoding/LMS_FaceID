from app.core.security import get_password_hash
from app.models.student import Student, StudentStatus
from app.models.user import User, UserRole


def test_student_search_and_filter(test_client, admin_headers, db_session):
    # Seed 3 sinh viên vào database test
    for i in range(1, 4):
        code = f"SVTEST{i:03d}"
        uname = code.lower()
        if not db_session.query(User).filter(User.username == uname).first():
            u = User(
                username=uname,
                email=f"{uname}@lms_test.local",
                password_hash=get_password_hash("Demo@123"),
                role=UserRole.student,
                is_active=True,
                must_change_password=False,
                is_deleted=False,
                token_version=1,
            )
            db_session.add(u)
            db_session.flush()

            st = Student(
                user_id=u.id,
                student_code=code,
                full_name=f"Sinh Vien Test {i}",
                admin_class="K65-CNTT",
                status=StudentStatus.studying if i < 3 else StudentStatus.graduated,
                is_deleted=False,
            )
            db_session.add(st)
    db_session.commit()

    # 1. Tìm theo mã SV
    resp = test_client.get("/api/v1/students?search=SVTEST001", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(s["student_code"] == "SVTEST001" for s in data["items"])

    # 2. Tìm theo họ tên
    resp = test_client.get("/api/v1/students?search=Sinh Vien Test 2", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(s["student_code"] == "SVTEST002" for s in data["items"])

    # 3. Lọc theo trạng thái
    resp = test_client.get("/api/v1/students?status=graduated", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["status"] == "graduated" for s in data["items"])

    # 4. Kết hợp tìm kiếm + lọc trạng thái
    resp = test_client.get("/api/v1/students?search=SVTEST001&status=studying", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["student_code"] == "SVTEST001"

    # 5. Không tìm thấy kết quả
    resp = test_client.get("/api/v1/students?search=KHONG_TON_TAI_9999", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0

    # 6. Phân trang
    resp = test_client.get("/api/v1/students?search=SVTEST&page=1&page_size=2", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
